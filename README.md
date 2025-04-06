# 🖐️ HandWave Unlock 🔓

Unlock your system using **hand gestures**! This project uses computer vision and AI to detect specific hand wave gestures via your webcam and unlocks the system securely.

## 🚀 Features

- ✋ Real-time hand gesture detection using **MediaPipe**
- 🔐 Unlock system functionality through specific hand waves
- 🎥 Uses **OpenCV** for live webcam feed
- 🖱️ Automates input using **PyAutoGUI**
- 🌐 Simple web interface using **Flask**

---

## 📂 Project Structure

```
HandWave_Unlock/
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── templates/
│   └── (HTML files here)
│
├── app.py
├── main.py
├── requirements.txt
└── README.md
```

---

## 🧠 Tech Stack

- **Python**
- **Flask**
- **OpenCV**
- **MediaPipe**
- **PyAutoGUI**

---

## 🛠️ Installation

1. 🔽 Clone the repo  
```bash
git clone https://github.com/balu-16/HandWave_Unlock.git
```
```bash
cd HandWave_Unlock
```
📦 Install dependencies

```bash
pip install -r requirements.txt
```
▶️ Run the app

```bash
python main.py
```
🌐 Open in your browser

```bash
http://localhost:5000
```
🖥️ Deployment (Render)
Add gunicorn to requirements.txt:

```bash
gunicorn==20.1.0
```
Set Start Command on Render:

```bash
gunicorn main:app
```

🤝 Contributions
Pull requests are welcome! Feel free to open an issue for feature suggestions or bugs.
