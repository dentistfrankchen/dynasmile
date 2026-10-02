"""Interactive AWS provisioning and connection support for Dynasmile."""

import configparser
import json
import os
import socket
import stat
import threading
import time
import urllib.request
from pathlib import Path

import boto3
import paramiko
from botocore.exceptions import ClientError, ProfileNotFound
from PyQt5 import QtCore, QtWidgets

from .forward import ForwardServer, Handler


APP_TAG = "Dynasmile"
DEFAULT_REGION = "us-east-1"
DEFAULT_INSTANCE_TYPE = "g4dn.xlarge"
CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Dynasmile"
CONFIG_FILE = CONFIG_DIR / "aws_ec2.json"
CREDENTIALS_FILE = Path.home() / ".aws" / "credentials"


class AWSManager:
    def __init__(self, config=None):
        self.config = config or self.load_config()
        self.session = None
        self.ec2 = None
        self.s3 = None
        self.connection_error = None
        self._ssh = None
        self._tunnel = None
        if self.config:
            try:
                self.connect()
            except Exception as exc:
                self.connection_error = str(exc)

    @staticmethod
    def load_config():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, ValueError):
            return {}

    def save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as stream:
            json.dump(self.config, stream, indent=2)

    @staticmethod
    def save_credentials(profile, access_key, secret_key, session_token=""):
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        parser = configparser.RawConfigParser()
        if CREDENTIALS_FILE.exists():
            parser.read(str(CREDENTIALS_FILE), encoding="utf-8")
        if not parser.has_section(profile):
            parser.add_section(profile)
        parser.set(profile, "aws_access_key_id", access_key.strip())
        parser.set(profile, "aws_secret_access_key", secret_key.strip())
        if session_token.strip():
            parser.set(profile, "aws_session_token", session_token.strip())
        elif parser.has_option(profile, "aws_session_token"):
            parser.remove_option(profile, "aws_session_token")
        with CREDENTIALS_FILE.open("w", encoding="utf-8") as stream:
            parser.write(stream)

    def connect(self):
        profile = self.config.get("profile", "default")
        region = self.config.get("region", DEFAULT_REGION)
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.ec2 = self.session.client("ec2")
        self.s3 = self.session.client("s3")
        return self.session.client("sts").get_caller_identity()

    def discover_instances(self):
        reservations = self.ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
        ).get("Reservations", [])
        found = []
        for reservation in reservations:
            for instance in reservation.get("Instances", []):
                tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                found.append({
                    "id": instance["InstanceId"],
                    "name": tags.get("Name", ""),
                    "state": instance["State"]["Name"],
                    "type": instance["InstanceType"],
                    "dns": instance.get("PublicDnsName", ""),
                    "managed": tags.get("Application") == APP_TAG,
                })
        return sorted(found, key=lambda item: (not item["managed"], item["name"], item["id"]))

    def instance(self):
        instance_id = self.config.get("instance_id")
        if not instance_id:
            raise RuntimeError("No EC2 instance has been selected.")
        return self.session.resource("ec2").Instance(instance_id)

    def instance_status(self):
        instance = self.instance()
        instance.load()
        return instance.state["Name"], instance.public_dns_name or instance.public_ip_address or ""

    def start_instance(self):
        instance = self.instance()
        instance.load()
        if instance.state["Name"] == "stopped":
            instance.start()
        if instance.state["Name"] != "running":
            instance.wait_until_running()
        instance.reload()
        self.config["public_dns"] = instance.public_dns_name or instance.public_ip_address
        self.save_config()
        return self.config["public_dns"]

    def stop_instance(self):
        instance = self.instance()
        instance.load()
        if instance.state["Name"] in ("pending", "running"):
            instance.stop()

    def terminate_instance(self):
        instance = self.instance()
        instance.terminate()
        self.config.pop("instance_id", None)
        self.config.pop("public_dns", None)
        self.save_config()

    def _latest_deep_learning_ami(self):
        images = self.ec2.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "state", "Values": ["available"]},
                {"Name": "architecture", "Values": ["x86_64"]},
                {"Name": "name", "Values": ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04) *"]},
            ],
        )["Images"]
        if not images:
            raise RuntimeError("No AWS Deep Learning Ubuntu GPU AMI is available in this region.")
        return max(images, key=lambda image: image["CreationDate"])["ImageId"]

    def _default_vpc(self):
        vpcs = self.ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
        if not vpcs:
            raise RuntimeError("This region has no default VPC. Create a default VPC in AWS first.")
        return vpcs[0]["VpcId"]

    def _ensure_security_group(self):
        name = "dynasmile-client"
        vpc_id = self._default_vpc()
        groups = self.ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [name]}, {"Name": "vpc-id", "Values": [vpc_id]}]
        )["SecurityGroups"]
        if groups:
            return groups[0]["GroupId"]
        group_id = self.ec2.create_security_group(
            GroupName=name, Description="Dynasmile SSH tunnel", VpcId=vpc_id
        )["GroupId"]
        try:
            public_ip = urllib.request.urlopen("https://checkip.amazonaws.com", timeout=5).read().decode().strip()
            cidr = public_ip + "/32"
        except Exception:
            cidr = "0.0.0.0/0"
        self.ec2.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
                            "IpRanges": [{"CidrIp": cidr, "Description": "Dynasmile client"}]}],
        )
        self.ec2.create_tags(Resources=[group_id], Tags=[{"Key": "Application", "Value": APP_TAG}])
        return group_id

    def _ensure_key_pair(self):
        key_name = "dynasmile-client"
        key_path = CONFIG_DIR / "dynasmile-client.pem"
        existing = self.ec2.describe_key_pairs(Filters=[{"Name": "key-name", "Values": [key_name]}])["KeyPairs"]
        if existing and key_path.exists():
            return key_name, str(key_path)
        if existing:
            self.ec2.delete_key_pair(KeyName=key_name)
        material = self.ec2.create_key_pair(KeyName=key_name, KeyType="rsa")["KeyMaterial"]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        key_path.write_text(material, encoding="utf-8")
        try:
            key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        return key_name, str(key_path)

    def _ensure_bucket(self, account_id):
        requested = self.config.get("bucket", "").strip()
        bucket = requested or "dynasmile-{}-{}".format(account_id, self.config["region"]).lower()
        try:
            self.s3.head_bucket(Bucket=bucket)
        except ClientError:
            args = {"Bucket": bucket}
            if self.config["region"] != "us-east-1":
                args["CreateBucketConfiguration"] = {"LocationConstraint": self.config["region"]}
            self.s3.create_bucket(**args)
        self.config["bucket"] = bucket
        return bucket

    def _ensure_instance_profile(self, bucket):
        iam = self.session.client("iam")
        role_name = "DynasmileEC2Role"
        profile_name = "DynasmileEC2Profile"
        trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
                 "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        try:
            iam.get_role(RoleName=role_name)
        except iam.exceptions.NoSuchEntityException:
            iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust),
                            Description="Dynasmile EC2 service role")
        policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
                  "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"],
                  "Resource": ["arn:aws:s3:::" + bucket, "arn:aws:s3:::" + bucket + "/*"]}]}
        iam.put_role_policy(RoleName=role_name, PolicyName="DynasmileBucketAccess",
                            PolicyDocument=json.dumps(policy))
        try:
            profile = iam.get_instance_profile(InstanceProfileName=profile_name)["InstanceProfile"]
        except iam.exceptions.NoSuchEntityException:
            profile = iam.create_instance_profile(InstanceProfileName=profile_name)["InstanceProfile"]
        if not any(role["RoleName"] == role_name for role in profile.get("Roles", [])):
            iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)
            time.sleep(10)
        return profile_name

    @staticmethod
    def _user_data(bucket):
        return """#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/dynasmile-setup.log) 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git python3-venv python3-pip libgl1 libglib2.0-0
if [ ! -d /opt/dynasmile ]; then git clone https://github.com/dentistfrankchen/dynasmile.git /opt/dynasmile; fi
cd /opt/dynasmile
git pull --ff-only || true
python3 -m venv /opt/dynasmile-venv
/opt/dynasmile-venv/bin/pip install --upgrade pip wheel
/opt/dynasmile-venv/bin/pip install -r server/requirements.txt
sed -i "s/'frank--bucket'/'%s'/g" server/service.py
cat >/etc/systemd/system/dynasmile.service <<'EOF'
[Unit]
Description=Dynasmile analysis service
After=network-online.target
[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/dynasmile/server
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/dynasmile-venv/bin/python service.py
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now dynasmile
touch /var/lib/dynasmile-ready
""" % bucket

    def provision(self, instance_type=DEFAULT_INSTANCE_TYPE):
        identity = self.connect()
        bucket = self._ensure_bucket(identity["Account"])
        profile = self._ensure_instance_profile(bucket)
        security_group = self._ensure_security_group()
        key_name, key_path = self._ensure_key_pair()
        image_id = self._latest_deep_learning_ami()
        response = self.ec2.run_instances(
            ImageId=image_id, InstanceType=instance_type, MinCount=1, MaxCount=1,
            KeyName=key_name, SecurityGroupIds=[security_group],
            IamInstanceProfile={"Name": profile}, UserData=self._user_data(bucket),
            BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {
                "VolumeSize": 80, "VolumeType": "gp3", "DeleteOnTermination": True}}],
            TagSpecifications=[{"ResourceType": "instance", "Tags": [
                {"Key": "Name", "Value": "Dynasmile"}, {"Key": "Application", "Value": APP_TAG}]}],
        )
        self.config.update({"instance_id": response["Instances"][0]["InstanceId"],
                            "key_path": key_path, "ssh_user": "ubuntu",
                            "instance_type": instance_type, "stop_on_exit": True})
        self.save_config()
        return self.start_instance()

    def adopt_instance(self, instance_id):
        instance = self.session.resource("ec2").Instance(instance_id)
        instance.load()
        image = self.ec2.describe_images(ImageIds=[instance.image_id]).get("Images", [{}])[0]
        username = "ubuntu" if "ubuntu" in image.get("Name", "").lower() else "ec2-user"
        self.config.update({"instance_id": instance_id, "ssh_user": username,
                            "public_dns": instance.public_dns_name or instance.public_ip_address})
        self.save_config()

    def test_ssh(self):
        host = self.start_instance()
        key_path = self.config.get("key_path", "")
        if not key_path or not Path(key_path).exists():
            raise RuntimeError("Select the private key (.pem) for this EC2 instance.")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=self.config.get("ssh_user", "ubuntu"), key_filename=key_path,
                       timeout=15, banner_timeout=30)
        _, stdout, _ = client.exec_command("echo connected")
        result = stdout.read().decode().strip()
        client.close()
        return result == "connected"

    def open_tunnel(self, local_port=5000):
        host = self.start_instance()
        deadline = time.time() + 300
        last_error = None
        while time.time() < deadline:
            try:
                self._ssh = paramiko.SSHClient()
                self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self._ssh.connect(host, username=self.config.get("ssh_user", "ubuntu"),
                                  key_filename=self.config["key_path"], timeout=15, banner_timeout=30)
                break
            except Exception as exc:
                last_error = exc
                time.sleep(5)
        else:
            raise RuntimeError("SSH did not become ready: {}".format(last_error))
        self._ssh.exec_command("sudo systemctl start dynasmile 2>/dev/null || "
                               "(cd service && nohup python3 service.py >/tmp/dynasmile.log 2>&1 &)")

        class TunnelHandler(Handler):
            chain_host = "127.0.0.1"
            chain_port = 5000
            ssh_transport = self._ssh.get_transport()

        self._tunnel = ForwardServer(("127.0.0.1", local_port), TunnelHandler)
        threading.Thread(target=self._tunnel.serve_forever, daemon=True).start()
        deadline = time.time() + 1200
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", local_port), timeout=2):
                    return
            except OSError:
                time.sleep(5)
        raise RuntimeError("The Dynasmile service did not become ready in time.")

    def close(self, stop=None):
        if self._tunnel:
            self._tunnel.shutdown()
            self._tunnel.server_close()
            self._tunnel = None
        if self._ssh:
            self._ssh.close()
            self._ssh = None
        if stop is None:
            stop = self.config.get("stop_on_exit", True)
        if stop and self.config.get("instance_id"):
            self.stop_instance()


class AWSSetupDialog(QtWidgets.QDialog):
    configurationSaved = QtCore.pyqtSignal()

    def __init__(self, parent=None, manager=None, embedded=False):
        super().__init__(parent)
        self.embedded = embedded
        self.setWindowTitle("Dynasmile AWS/EC2 automatic setup")
        self.resize(760, 620)
        self.manager = manager or AWSManager()
        config = self.manager.config
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Enter an AWS profile or access keys, then choose an existing instance or create a complete "
            "Dynasmile GPU server automatically. Access keys are stored in the standard ~/.aws/credentials file."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self.profile = QtWidgets.QLineEdit(config.get("profile", "default"))
        self.region = QtWidgets.QComboBox()
        self.region.setEditable(True)
        self.region.addItems(["us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-central-1",
                              "ap-southeast-1", "ap-southeast-2", "ap-northeast-1"])
        self.region.setCurrentText(config.get("region", DEFAULT_REGION))
        self.access_key = QtWidgets.QLineEdit()
        self.secret_key = QtWidgets.QLineEdit()
        self.secret_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.session_token = QtWidgets.QLineEdit()
        self.session_token.setEchoMode(QtWidgets.QLineEdit.Password)
        self.instance_type = QtWidgets.QComboBox()
        self.instance_type.addItems(["g4dn.xlarge", "g4dn.2xlarge", "g5.xlarge", "g5.2xlarge"])
        self.instance_type.setCurrentText(config.get("instance_type", DEFAULT_INSTANCE_TYPE))
        self.ssh_user = QtWidgets.QLineEdit(config.get("ssh_user", "ubuntu"))
        self.key_path = QtWidgets.QLineEdit(config.get("key_path", ""))
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse_key)
        key_row = QtWidgets.QHBoxLayout()
        key_row.addWidget(self.key_path)
        key_row.addWidget(browse)
        self.stop_on_exit = QtWidgets.QCheckBox("Stop EC2 automatically when Dynasmile exits")
        self.stop_on_exit.setChecked(config.get("stop_on_exit", True))
        form.addRow("AWS profile:", self.profile)
        form.addRow("Region:", self.region)
        form.addRow("Access key (optional):", self.access_key)
        form.addRow("Secret key (optional):", self.secret_key)
        form.addRow("Session token (optional):", self.session_token)
        form.addRow("GPU instance type:", self.instance_type)
        form.addRow("SSH username:", self.ssh_user)
        form.addRow("Private key (.pem):", key_row)
        form.addRow("", self.stop_on_exit)
        layout.addLayout(form)
        actions = QtWidgets.QHBoxLayout()
        for text, slot in [("1. Validate AWS", self.validate_aws), ("2. Find instances", self.refresh_instances),
                           ("Create server automatically", self.create_server), ("Start", self.start_server),
                           ("Stop", self.stop_server), ("Test SSH", self.test_ssh)]:
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.instances = QtWidgets.QTableWidget(0, 5)
        self.instances.setHorizontalHeaderLabels(["Name", "Instance ID", "State", "Type", "Managed"])
        self.instances.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.instances.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.instances.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.instances.itemSelectionChanged.connect(self.select_instance)
        layout.addWidget(self.instances)
        self.status = QtWidgets.QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(120)
        layout.addWidget(self.status)
        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close)
        self.buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Save and use")
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.reject)
        if self.embedded:
            self.buttons.button(QtWidgets.QDialogButtonBox.Close).hide()
        layout.addWidget(self.buttons)

    def log(self, message):
        self.status.appendPlainText(str(message))
        QtWidgets.QApplication.processEvents()

    def _browse_key(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select EC2 private key", "", "PEM key (*.pem);;All files (*)")
        if path:
            self.key_path.setText(path)

    def _apply(self):
        profile = self.profile.text().strip() or "default"
        if self.access_key.text().strip() or self.secret_key.text().strip():
            if not self.access_key.text().strip() or not self.secret_key.text().strip():
                raise RuntimeError("Both the access key and secret key are required.")
            AWSManager.save_credentials(profile, self.access_key.text(), self.secret_key.text(), self.session_token.text())
        self.manager.config.update({"profile": profile, "region": self.region.currentText().strip(),
                                    "instance_type": self.instance_type.currentText(),
                                    "ssh_user": self.ssh_user.text().strip() or "ubuntu",
                                    "key_path": self.key_path.text().strip(),
                                    "stop_on_exit": self.stop_on_exit.isChecked()})
        self.manager.save_config()
        self.manager.connect()

    def _run(self, title, operation):
        try:
            self.setCursor(QtCore.Qt.WaitCursor)
            self._apply()
            result = operation()
            self.log("{}: OK{}".format(title, " — " + str(result) if result else ""))
            return result
        except (ClientError, ProfileNotFound, Exception) as exc:
            self.log("{}: FAILED — {}".format(title, exc))
            QtWidgets.QMessageBox.critical(self, title, str(exc))
        finally:
            self.unsetCursor()

    def validate_aws(self):
        identity = self._run("AWS credentials", self.manager.connect)
        if identity:
            self.log("Account: {}".format(identity.get("Account")))

    def refresh_instances(self):
        found = self._run("Instance discovery", self.manager.discover_instances)
        if found is None:
            return
        self.instances.setRowCount(len(found))
        for row, item in enumerate(found):
            values = [item["name"], item["id"], item["state"], item["type"], "Yes" if item["managed"] else "No"]
            for column, value in enumerate(values):
                self.instances.setItem(row, column, QtWidgets.QTableWidgetItem(value))
        selected = self.manager.config.get("instance_id")
        for row in range(self.instances.rowCount()):
            if self.instances.item(row, 1).text() == selected:
                self.instances.selectRow(row)

    def select_instance(self):
        row = self.instances.currentRow()
        if row >= 0:
            try:
                self._apply()
                self.manager.adopt_instance(self.instances.item(row, 1).text())
                self.ssh_user.setText(self.manager.config.get("ssh_user", "ubuntu"))
                self.log("Selected {}".format(self.manager.config["instance_id"]))
            except Exception as exc:
                self.log("Selection failed: {}".format(exc))

    def create_server(self):
        answer = QtWidgets.QMessageBox.question(
            self, "Create EC2 server",
            "This creates a billable GPU instance, an S3 bucket, IAM role, security group, and SSH key. Continue?"
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        self._run("EC2 provisioning", lambda: self.manager.provision(self.instance_type.currentText()))
        self.key_path.setText(self.manager.config.get("key_path", ""))
        self.ssh_user.setText(self.manager.config.get("ssh_user", "ubuntu"))
        self.refresh_instances()

    def start_server(self):
        self._run("Start EC2", self.manager.start_instance)
        self.refresh_instances()

    def stop_server(self):
        self._run("Stop EC2", self.manager.stop_instance)
        self.refresh_instances()

    def test_ssh(self):
        self._run("SSH connection", self.manager.test_ssh)

    def save_and_accept(self):
        try:
            self._apply()
            if not self.manager.config.get("instance_id"):
                raise RuntimeError("Select or create an EC2 instance first.")
            if not self.manager.config.get("key_path"):
                raise RuntimeError("Select the EC2 private key first.")
            os.environ["DYNASMILE_BUCKET"] = self.manager.config.get("bucket", "frank--bucket")
            self.configurationSaved.emit()
            if not self.embedded:
                self.accept()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Configuration", str(exc))
