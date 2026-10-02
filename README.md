⭐ Star Dynasmile on GitHub — it motivates us a lot!

**DynaSmile is an open-source, AI-powered video analysis software designed for the aesthetic evaluation of dynamic smiles in orthodontics.** It helps dental researchers identify peak-smile frames, detect dentofacial landmarks, and quantify clinically relevant smile measurements.

If DynaSmile supports your research, please cite the peer-reviewed SoftwareX article: Chen K, Qiu L, Xie X, Bai Y. *Dynasmile: Video-based smile analysis software in orthodontics*. SoftwareX. 2025;29:102004. [https://doi.org/10.1016/j.softx.2024.102004](https://doi.org/10.1016/j.softx.2024.102004)

[![Share](https://img.shields.io/badge/share-000000?logo=x&logoColor=white)](https://x.com/intent/tweet?text=Check%20out%20this%20project%20on%20GitHub:%20https://github.com/dentistfrankchen/dynasmile%20%23Orthodontics%20%23Dentistry%20%23SmileAnalysis)
[![Share](https://img.shields.io/badge/share-1877F2?logo=facebook&logoColor=white)](https://www.facebook.com/sharer/sharer.php?u=https://github.com/dentistfrankchen/dynasmile)
[![Share](https://img.shields.io/badge/share-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/sharing/share-offsite/?url=https://github.com/dentistfrankchen/dynasmile)
[![Share](https://img.shields.io/badge/share-FF4500?logo=reddit&logoColor=white)](https://www.reddit.com/submit?title=Check%20out%20this%20project%20on%20GitHub:%20https://github.com/dentistfrankchen/dynasmile)
[![Share](https://img.shields.io/badge/share-0088CC?logo=telegram&logoColor=white)](https://t.me/share/url?url=https://github.com/dentistfrankchen/dynasmile&text=Check%20out%20this%20project%20on%20GitHub)

## Table of Contents
- [Features highlight](#-features-highlight)
- [Functionality](#-functionality)
- [How to Install](#-how-to-install)
- [How to run the program](#-how-to-run-the-program)
- [Feedback and Contributions](#-feedback-and-contributions)
- [License](#-license)
- [Contacts](#%EF%B8%8F-contacts)

## 🚀 Features highlight

**Dynasmile** is a Python-based AI-driven dynamic smile analysis tool for dental research. It uses computer vision techniques to analyze smile process. As a dental application, it features:

- **Smile intensity estimation**: Dynasmile automatically analyzes the smile intensity across different frames of the video. It plots the smile intensity, which helps the dentist to locate the frame where the smile reaches its peak.

- **Landmark detecion and display**: Dynasmile detects dentofacial landmarks on patients' faces and overlays the result to the selected frame, providing a user-friendly interface for dental specialists.

- **Low cost**: Dynasmile do not rely on local graphical card. The special architecture of this software relies on EC2 server, which can be rent at low cost and used at any time.

## 🎓 Functionality

Dynasmile processes the video uploaded by the user. It performs smile analysis on the selected frame, which includes detection of 13 dentofacial landmarks and performing 8 smile measurements.

For convenience, all the information is provided in the tables below:

### Dentofacial landmarks
|Number|Landmark name|
|:-|:-|
|1|Subnasale|
|2|Inferior upper lip border|
|3|Superior lower lip border|
|4|Right outer canthus|
|5|Left outer canthus| 
|6|Right outer smile commissure|
|7|Left outer smile sommissure|
|8|Soft tissue nasion|
|9|Soft tissue pogonion|
|10|Incisor edge| 
|11|Left upper cuspid tip|
|12|Right upper cuspid tip|
|13|Cervical part of incisor| 
|**In total 13 landmarks**|

### Smile measurements
|Number|Measurement name|
|:-|:-|
|1|Intercommissure width|
|2|Interlabial gap|
|3|Gingival display|
|4|Philtrum height|
|5|Transverse symmetry| 
|6|Vertical symmetry|
|7|Dental angulation|
|8|Canthus and smile commissure deviation|
|**In total 8 measurements**|


## 📝 How to Install
> [!IMPORTANT]
> This program relies on AWS EC2 GPU web instance to run, if you are new to EC2, please refer to this website https://aws.amazon.com/ec2/getting-started/

### Dependency: Using our pre-configured EC2 instance
> [!IMPORTANT]
> Since our computing resource is limited, the instance might be temporarily stopped anytime.

```shell
# Ensure Git is installed
# Visit https://git-scm.com to download and install console Git if not already installed
# Clone the repository to local computer
git clone https://github.com/dentistfrankchen/dynasmile.git

# Navigate to the project directory(.../dynasmile-master)
cd Path/to/dynasmile-master

# Activate the virtual environment
.\venv\Scripts\activate

# Install the requirements for the local interface.
pip install -r requirements.txt

```



## 📚 How to run the program 

### Step 1: Start main.py and connect to the EC2 instance.
```shell
# Open Command Prompt.

# Assuming you have activated the virtual environment.

# You can start the main interface now.
python .\client\software\main.py

```

### Step 2: Wait for the main.py to connect to EC2 instance.
During this process, the mian.py will open command prompt windows to automatically connect to 
the EC2 instance.

**Then you need to wait for the connection.**
**Please do not close the windows of command prompt.**

When the connection is finished, the mian interface would pop up.

### Step 3: Use the interface to conduct smile analysis.
1. Upload a video by clicking **Drag and Drop panel**.
2. The program then uploads the video, displaying the process through the **progress bar**.
3. When the progress bar reaches 100 percent, frame with greatest smile intensity will be automatically displayed.
4. The landmarks and measurements will be automatically displayed.
5. The user clicks the **'Save csv'** button, and the coordinates of the landmarks as well as the measurements will be saved in CSV files.

For a real-time view, here's a video for how to run this program:

https://github.com/user-attachments/assets/79f666d3-ec7a-4db0-8ec4-c57b7f8d55bb

## 🤝 Feedback and Contributions

We've made a lot of effort to implement many aspects of dynamic smile analysis in this software. However, the development journey doesn't end now, and your feedback is crucial for our further improvement.

**What is DynaSmile used for?** DynaSmile supports video-based dynamic smile analysis in orthodontic and dental research. It converts a smile video into a reproducible peak-smile frame with landmark overlays and quantitative measurements.

**How does DynaSmile evaluate a dynamic smile?** It estimates smile intensity across video frames, selects the frame with the greatest smile intensity, detects 13 dentofacial landmarks, and calculates 8 smile measurements.

**Does DynaSmile require a local GPU?** No. The desktop client is designed to use an AWS EC2 GPU instance for compute-intensive analysis, allowing researchers without a dedicated local graphics card to run the workflow.

**Can DynaSmile compare orthodontic treatment outcomes?** Researchers can export landmark coordinates and measurements as CSV files for quantitative comparison of dynamic smile characteristics across time points or study groups. DynaSmile is a research tool and does not replace professional diagnosis or clinical judgment.

**How should DynaSmile be cited?** Cite the SoftwareX publication using DOI [10.1016/j.softx.2024.102004](https://doi.org/10.1016/j.softx.2024.102004). Machine-readable citation metadata are also provided in `CITATION.cff`.

> [!IMPORTANT]
> Whether you have feedback on improvements, have encountered any bugs, or have suggestions for features, we cannot wait to hear from you. Your insights help us get our software more robust and user-friendly.

Please feel free to contribute by [submitting an issue](https://github.com/dentistfrankchen/dynasmile/issues). Each contribution helps us get better and improve.

We appreciate your kindly support and look forward to build our product even better with your help!

## 📃 License

This product is distributed under Apache license.

For non-commercial use, this product is available for free.

## 🗨️ Contacts

For more details about our products, services, or any general information regarding the Amazon EC2 server, feel free to contact us. We are here to provide needed support and answer any questions you have. Below are the best ways to contact our team:

- **Email**: Send us your inquiries or support requests at [dentistfrankchen@outlook.com](mailto:dentistfrankchen@outlook.com).


We look forward to assisting you and keeping your experience with our applicaion being enjoyable!

[Back to top](#top)
