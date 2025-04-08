from flask import Flask, render_template, Response, jsonify, request
import cv2
import mediapipe as mp
import time
# import pyautogui
import threading
import queue
import logging
import sys
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables
gesture_sequence, attempts, success, last_gesture = [], 3, False, None
last_detection_time = time.time()
frame_queue = queue.Queue()
gesture_status = {"status": "waiting",
                  "message": "Click 'Start Recognition' to begin"}
camera_error, is_recognition_active = False, False
camera, gesture_thread = None, None

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def reset_recognition():
    global gesture_sequence, attempts, success, last_gesture, last_detection_time, gesture_status, camera_error, is_recognition_active
    gesture_sequence, attempts, success = [], 3, False
    last_gesture, last_detection_time = None, time.time()
    gesture_status = {"status": "waiting",
                      "message": "Click 'Start Recognition' to begin"}
    camera_error, is_recognition_active = False, False


def release_camera():
    global camera
    if camera is not None:
        try:
            camera.release()
            logger.info("Camera released")
        except Exception as e:
            logger.warning(f"Error releasing camera: {str(e)}")
        finally:
            camera = None


def force_camera_release():
    """Release camera resources"""
    global camera
    release_camera()
    cv2.destroyAllWindows()
    time.sleep(0.5)

# Gesture detection functions


def is_peace_sign(landmarks):
    return (landmarks[8].y < landmarks[6].y and
            landmarks[12].y < landmarks[10].y and
            landmarks[16].y > landmarks[14].y and
            landmarks[20].y > landmarks[18].y and
            landmarks[4].x < landmarks[3].x)


def is_all_fingers_open(landmarks):
    return (landmarks[8].y < landmarks[6].y and
            landmarks[12].y < landmarks[10].y and
            landmarks[16].y < landmarks[14].y and
            landmarks[20].y < landmarks[18].y and
            landmarks[4].y < landmarks[2].y)


def is_fist(landmarks):
    return all(landmarks[tip].y > landmarks[joint].y for tip, joint in [(8, 6), (12, 10), (16, 14), (20, 18), (4, 2)])

# I am commenting the unlocking part to deploy it in render
# def unlock_laptop():
#     try:
#         time.sleep(1)
#         pyautogui.write("your_laptopPassword")
#         pyautogui.press("enter")
#         logger.info("Laptop unlocked successfully")
#     except Exception as e:
#         logger.error(f"Error unlocking laptop: {str(e)}")
#         gesture_status["message"] = "Error unlocking laptop"


def process_gestures():
    global gesture_sequence, attempts, success, last_gesture, last_detection_time, gesture_status, camera_error, is_recognition_active, camera

    start_time = time.time()
    frame_count = 0

    try:
        logger.info("Starting gesture processing...")
        force_camera_release()  # Clean up any existing camera instance

        # Try different camera initialization methods
        for camera_init in [
            lambda: cv2.VideoCapture(0, cv2.CAP_DSHOW),
            lambda: cv2.VideoCapture(0)
        ]:
            try:
                camera = camera_init()
                time.sleep(0.3)  # Give camera time to initialize
                if camera and camera.isOpened():
                    break
            except Exception as e:
                logger.warning(f"Camera init method failed: {str(e)}")

        # Verify camera is working
        if camera is None or not camera.isOpened():
            raise Exception(
                "Could not open camera. Please make sure your camera is connected and not being used by another application.")

        # Try to get a test frame
        ret, test_frame = camera.read()
        if not ret or test_frame is None or test_frame.size == 0:
            raise Exception(
                "Camera connection successful but could not read frames. Try restarting your computer.")

        # Set camera properties for better performance
        for prop, value in [
            (cv2.CAP_PROP_FRAME_WIDTH, 320),
            (cv2.CAP_PROP_FRAME_HEIGHT, 240),
            (cv2.CAP_PROP_FPS, 30),
            (cv2.CAP_PROP_BUFFERSIZE, 1),
            (cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        ]:
            try:
                camera.set(prop, value)
            except Exception:
                pass  # Continue if one property can't be set

        # Add a starting frame to queue
        signal_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(signal_frame, "Camera Started", (90, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        frame_queue.put(signal_frame)

        # Initialize MediaPipe with performance options
        with mp_hands.Hands(
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
            max_num_hands=1,
            model_complexity=0
        ) as hands:
            # Update status
            gesture_status["message"] = "Camera ready - show gestures"

            # Processing variables
            skip_frames, frame_counter = 1, 0
            prev_frame_time = time.time()

            # Main processing loop
            while is_recognition_active and not success and attempts > 0 and camera is not None:
                # Check camera and capture frame
                if not camera.isOpened():
                    gesture_status.update(
                        {"status": "error", "message": "Camera error: Camera was closed unexpectedly"})
                    break

                ret, frame = camera.read()
                if not ret or frame is None or frame.size == 0:
                    gesture_status.update(
                        {"status": "error", "message": "Camera error: Failed to grab frame"})
                    break

                # Update frame counters and timing
                frame_counter += 1
                frame_count += 1
                current_time = time.time()
                fps = 1 / \
                    (current_time - prev_frame_time) if (current_time -
                                                         prev_frame_time) > 0 else 30
                prev_frame_time = current_time

                # Flip frame for display
                frame = cv2.flip(frame, 1)
                output_frame = frame.copy()

                # Process with MediaPipe on selected frames
                if frame_counter % skip_frames == 0:
                    try:
                        # Process frame
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        small_rgb = cv2.resize(rgb_frame, (160, 120))
                        results = hands.process(small_rgb)

                        # Add text overlays
                        for idx, text in enumerate([
                            ("Processing: Active", 30),
                            (f"Gestures: {', '.join(gesture_sequence) if gesture_sequence else 'None'}", 60),
                            (f"FPS: {round(fps, 1)}", 90)
                        ]):
                            cv2.putText(output_frame, text[0], (85, text[1]),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

                        # Process detected hands
                        if results.multi_hand_landmarks:
                            for hand_landmarks in results.multi_hand_landmarks:
                                # Draw landmarks
                                mp_drawing.draw_landmarks(
                                    output_frame, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                                    mp_drawing.DrawingSpec(
                                        color=(0, 255, 0), thickness=1, circle_radius=1),
                                    mp_drawing.DrawingSpec(
                                        color=(0, 0, 255), thickness=1)
                                )
                                landmarks = hand_landmarks.landmark

                                # Detect gestures
                                gesture_map = {
                                    "peace": is_peace_sign(landmarks),
                                    "open": is_all_fingers_open(landmarks),
                                    "fist": is_fist(landmarks)
                                }

                                current_gesture = next((gesture for gesture, detected in gesture_map.items()
                                                        if detected), None)

                                # Update sequence if new gesture detected
                                if current_gesture and current_gesture != last_gesture:
                                    gesture_sequence.append(current_gesture)
                                    gesture_status["message"] = f"{current_gesture.capitalize()} Gesture Detected"

                                    # Display detected gesture
                                    gesture_indicator = f"DETECTED: {current_gesture.upper()}"
                                    text_size = cv2.getTextSize(
                                        gesture_indicator, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                                    text_x = (
                                        output_frame.shape[1] - text_size[0]) // 2
                                    cv2.putText(output_frame, gesture_indicator, (text_x, 20),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

                                    last_gesture = current_gesture
                                    logger.info(
                                        f"Detected gesture: {current_gesture}")

                                # Check for successful sequence
                                if len(gesture_sequence) >= 3 and set(gesture_sequence[-3:]) == {"peace", "open", "fist"}:
                                    gesture_status.update(
                                        {"status": "success", "message": "✅ Gesture Matched! Unlocking Laptop..."})
                                    success = True
                                    unlock_laptop()
                                    break

                                last_detection_time = time.time()

                        # Reset if user takes too long
                        if time.time() - last_detection_time > 5 and len(gesture_sequence) < 3:
                            attempts -= 1
                            gesture_status["message"] = f"Attempts remaining: {attempts}"
                            gesture_sequence.clear()
                            last_gesture = None
                            last_detection_time = time.time()

                            if attempts == 0:
                                gesture_status.update(
                                    {"status": "error", "message": "❌ Maximum attempts reached. Access Denied."})
                                break

                    except Exception as e:
                        logger.error(f"Error processing frame: {str(e)}")

                # Log FPS periodically and add frame to queue
                if frame_count % 60 == 0:
                    logger.info(
                        f"Camera running at {fps:.2f} FPS, processed {frame_count} frames")

                frame_queue.put(output_frame)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in process_gestures: {error_msg}")
        camera_error = True
        gesture_status.update(
            {"status": "error", "message": f"Error accessing camera: {error_msg}"})
    finally:
        release_camera()
        is_recognition_active = False
        logger.info("Gesture processing ended")


@app.route('/')
def index():
    return render_template('index.html')


def generate_frames():
    global frame_queue, camera_error, is_recognition_active
    logger.info("Starting frame generation for video feed")

    # Create and encode default frame
    default_frame = np.ones((240, 320, 3), dtype=np.uint8) * 245
    text = "Click 'Start Recognition'"
    font, font_scale, font_thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
    text_x, text_y = (default_frame.shape[1] - text_size[0]
                      ) // 2, (default_frame.shape[0] + text_size[1]) // 2
    cv2.putText(default_frame, text, (text_x, text_y), font,
                font_scale, (70, 70, 70), font_thickness, cv2.LINE_AA)

    ret, default_encoded = cv2.imencode(
        '.jpg', default_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    default_frame_data = (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                          (default_encoded.tobytes() if ret else b'') + b'\r\n')

    # First yield the default frame
    yield default_frame_data

    # Continue with regular frame processing
    while True:
        try:
            # Get frame with short timeout
            frame = frame_queue.get(timeout=0.1)

            if frame is None:
                yield default_frame_data
                continue

            # Encode and yield the frame
            ret, buffer = cv2.imencode(
                '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                yield default_frame_data
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        except queue.Empty:
            # Return default frame if queue is empty and recognition not active
            if not is_recognition_active:
                yield default_frame_data
        except Exception as e:
            logger.error(f"Error in generate_frames: {str(e)}")
            yield default_frame_data
            time.sleep(0.1)


@app.route('/video_feed')
def video_feed():
    logger.info("Video feed requested")
    try:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        logger.error(f"Error in video_feed route: {str(e)}")
        return "Video feed error", 500


@app.route('/gesture_status')
def get_gesture_status():
    return jsonify(gesture_status)


@app.route('/start_recognition', methods=['POST'])
def start_recognition():
    global is_recognition_active, gesture_thread

    # Ensure previous resources are cleaned up
    if gesture_thread and gesture_thread.is_alive():
        logger.info("Previous gesture thread still running, stopping it first")
        is_recognition_active = False
        try:
            gesture_thread.join(timeout=2.0)
        except Exception as e:
            logger.warning(f"Error joining previous thread: {str(e)}")

    force_camera_release()

    # Start recognition
    try:
        reset_recognition()
        is_recognition_active = True
        gesture_status["message"] = "Initializing camera..."

        gesture_thread = threading.Thread(target=process_gestures)
        gesture_thread.daemon = True
        gesture_thread.start()

        time.sleep(0.5)  # Brief wait for camera initialization
        logger.info("Recognition thread started")
        return jsonify({"status": "success", "message": "Recognition started"})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error starting recognition: {error_msg}")
        is_recognition_active = False
        gesture_status.update(
            {"status": "error", "message": f"Error starting recognition: {error_msg}"})
        return jsonify({"status": "error", "message": f"Failed to start recognition: {error_msg}"})


@app.route('/stop_recognition', methods=['POST'])
def stop_recognition():
    global is_recognition_active, gesture_thread
    if is_recognition_active:
        is_recognition_active = False
        if gesture_thread and gesture_thread.is_alive():
            gesture_thread.join(timeout=1.0)
        release_camera()
        reset_recognition()
        return jsonify({"status": "success", "message": "Recognition stopped"})
    return jsonify({"status": "error", "message": "Recognition not running"})


@app.teardown_appcontext
def cleanup(error):
    if error is not None:
        logger.info(f"Application context teardown with error: {error}")
        global is_recognition_active, gesture_thread
        is_recognition_active = False
        if gesture_thread and gesture_thread.is_alive():
            gesture_thread.join(timeout=1.0)
        force_camera_release()


if __name__ == '__main__':
    try:
        logger.info("Starting HandWave Unlock application...")
        force_camera_release()  # Force cleanup at start
        app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        cleanup(e)
        sys.exit(1)
