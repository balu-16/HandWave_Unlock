import cv2
import mediapipe as mp
import time
import os  # For system commands
import pyautogui  # For simulating keyboard input

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

gesture_sequence = []  # Stores detected gestures in order
attempts = 3  # Maximum attempts
success = False  # Stops detection after success
last_gesture = None  # Tracks last detected gesture
last_detection_time = time.time()  # Timer for gesture sequence


def unlock_laptop():
    # Using pyautogui to type the password
    time.sleep(1)  # Small delay to ensure proper execution
    pyautogui.write("81849")  # Type the password
    pyautogui.press("enter")  # Press Enter to unlock

    # Using nircmd (Commented Out)
    # os.system('nircmd.exe sendkeypress "8" "1" "8" "4" "9" "enter"')  # Entering the PIN


def is_peace_sign(landmarks):
    """Detects Peace Sign ✌️ (Index & Middle fingers up, others down)"""
    index_tip, middle_tip = landmarks[8], landmarks[12]
    ring_tip, pinky_tip = landmarks[16], landmarks[20]
    thumb_tip = landmarks[4]

    return (index_tip.y < landmarks[6].y and
            middle_tip.y < landmarks[10].y and
            ring_tip.y > landmarks[14].y and
            pinky_tip.y > landmarks[18].y and
            thumb_tip.x < landmarks[3].x)


def is_all_fingers_open(landmarks):
    """Detects All Fingers Open 🖐️"""
    return (landmarks[8].y < landmarks[6].y and
            landmarks[12].y < landmarks[10].y and
            landmarks[16].y < landmarks[14].y and
            landmarks[20].y < landmarks[18].y and
            landmarks[4].y < landmarks[2].y)


def is_fist(landmarks):
    """Detects Fist ✊ (All Fingers Closed)"""
    return (landmarks[8].y > landmarks[6].y and
            landmarks[12].y > landmarks[10].y and
            landmarks[16].y > landmarks[14].y and
            landmarks[20].y > landmarks[18].y and
            landmarks[4].y > landmarks[2].y)


cap = cv2.VideoCapture(0)

with mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7) as hands:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        if success:
            cv2.putText(frame, "SUCCESS!", (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow('Hand Gesture Recognition', frame)
            cv2.waitKey(2000)  # Show success message for 2 seconds
            break  # Stop program after success

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                landmarks = hand_landmarks.landmark

                current_gesture = None  # Reset current gesture

                if is_peace_sign(landmarks):
                    current_gesture = "peace"

                if is_all_fingers_open(landmarks):
                    current_gesture = "open"

                if is_fist(landmarks):
                    current_gesture = "fist"

                # Avoid adding repeated gestures
                if current_gesture and current_gesture != last_gesture:
                    gesture_sequence.append(current_gesture)
                    print(f"{current_gesture.capitalize()} Gesture Detected")
                    last_gesture = current_gesture  # Update last gesture

                # If user completes the sequence, unlock the laptop
                if set(gesture_sequence) == {"peace", "open", "fist"}:
                    print("✅ Gesture Matched! Unlocking Laptop...")
                    success = True
                    unlock_laptop()  # Unlock using pyautogui
                    break  # Exit loop immediately

                last_detection_time = time.time()  # Reset timer when gesture detected

        # Reset if user takes too long
        if time.time() - last_detection_time > 5 and len(gesture_sequence) < 3:
            attempts -= 1
            print(f"Attempts remaining: {attempts}")
            gesture_sequence.clear()
            last_detection_time = time.time()

            if attempts == 0:
                print("❌ Maximum attempts reached. Access Denied.")
                break  # Stop program after max attempts

        cv2.imshow('Hand Gesture Recognition', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
