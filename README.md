# 🖐️ HandWave Unlock 🔓

Unlock your system using **hand gestures**! This project uses computer vision and AI to detect specific hand wave gestures via your webcam and unlocks the system securely.

## 🚀 Features

- ✋ Real-time hand gesture detection using **MediaPipe**
- 🔐 Unlock system functionality through specific hand waves
- 🎥 Uses **OpenCV** for live webcam feed
- 🖱️ Automates input using **PyAutoGUI**
- 🌐 Simple web interface using **Flask**

---
## ✅ Prerequisites

Before you begin, ensure you have the following installed:

- 🐍 Python 3.6 or higher
- 📦 pip (Python package manager)
- 💻 Webcam (for gesture detection)
- 🧰 Git (optional, for cloning the repo)

Install the dependencies with:

```bash
pip install -r requirements.txt
```
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
---

## 🖥️ Deployment (Render)
Add gunicorn to requirements.txt:

```bash
gunicorn==20.1.0
```
Set Start Command on Render:

```bash
gunicorn main:app
```
---

## 🔮 Future Improvements

Here are a few ideas for improving the HandWave_Unlock project:

- 🔐 **Advanced security** – Add face recognition along with hand gestures for dual authentication.
- 🌐 **Web deployment** – Fully host the app online with live webcam streaming.
- 📱 **Mobile support** – Build a mobile version using Flask + Android camera.
- 🧠 **Gesture training** – Allow users to train and save their own custom gestures.
- 🔊 **Voice assistant integration** – Add voice command recognition for multi-modal interaction.
- 🎨 **Better UI** – Create a more polished and responsive front-end using React or modern CSS frameworks.

---

## 🤝 Contributions

Contributions are welcome and appreciated! 🎉

If you'd like to contribute to **HandWave_Unlock**, please follow these steps:

1. 🍴 Fork the repository  
2. 👯 Clone your forked repo  
```bash
git clone https://github.com/your-username/HandWave_Unlock.git
```
3. 💡 Create a new branch  
```bash
git checkout -b feature/YourFeatureName
```
4. 🛠️ Make your changes  
5. ✅ Commit your changes  
```bash
git commit -m "Add: Your meaningful commit message"
```
6. 🚀 Push to the branch  
```bash
git push origin feature/YourFeatureName
```
7. 📬 Open a Pull Request

---

## License
This project is licensed as **proprietary and confidential**.  
**You may not reuse, modify, or redistribute any part of this code.**
