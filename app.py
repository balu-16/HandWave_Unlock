from flask import Flask, render_template, Response, jsonify, request
import cv2
import mediapipe as mp
import time
import os
import sys
import atexit
import threading
import queue
import logging
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Thread lock for ALL shared mutable state
_state_lock = threading.Lock()

# Global variables
gesture_sequence = []
attempts = 3
success = False
last_gesture = None
last_detection_time = time.time()
frame_queue = queue.Queue(maxsize=10)
gesture_status = {"status": "waiting",
                  "message": "Click 'Start Recognition' to begin"}
camera_error = False
is_recognition_active = False
camera = None
gesture_thread = None

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def reset_recognition():
    global gesture_sequence, attempts, success, last_gesture, last_detection_time, gesture_status, camera_error, is_recognition_active
    with _state_lock:
        gesture_sequence = []
        attempts = 3
        success = False
        last_gesture = None
        last_detection_time = time.time()
        gesture_status = {"status": "waiting",
                          "message": "Click 'Start Recognition' to begin"}
        camera_error = False
        is_recognition_active = False
    # Drain frame_queue outside lock to avoid holding it during queue ops
    _drain_queue()


def _drain_queue():
    """Drain all items from frame_queue."""
    try:
        while True:
            frame_queue.get_nowait()
    except queue.Empty:
        pass


def release_camera():
    global camera
    with _state_lock:
        cam = camera
        camera = None
    if cam is not None:
        try:
            cam.release()
            logger.info("Camera released")
        except Exception as e:
            logger.warning(f"Error releasing camera: {str(e)}")


def force_camera_release():
    """Release camera resources"""
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

def unlock_laptop():
    """Unlock laptop using environment-configured password.

    Requires UNLOCK_PASSWORD environment variable to be set and
    pyautogui to be installed. Both are optional -- if either is
    missing the function logs a warning and returns gracefully.
    """
    password = os.environ.get("UNLOCK_PASSWORD", "")
    if not password:
        logger.warning(
            "UNLOCK_PASSWORD not set -- skipping system unlock. "
            "Set UNLOCK_PASSWORD env var to enable laptop unlock."
        )
        return

    try:
        import pyautogui
    except ImportError:
        logger.warning(
            "pyautogui is not installed -- skipping system unlock. "
            "Install pyautogui to enable laptop unlock."
        )
        return

    try:
        time.sleep(1)
        pyautogui.write(password)
        pyautogui.press("enter")
        logger.info("Laptop unlocked successfully")
    except Exception as e:
        logger.error(f"Error unlocking laptop: {str(e)}")
        with _state_lock:
            gesture_status["message"] = "Error unlocking laptop"


def process_gestures():
    global gesture_sequence, attempts, success, last_gesture, last_detection_time, gesture_status, camera_error, is_recognition_active, camera

    start_time = time.time()
    frame_count = 0

    try:
        logger.info("Starting gesture processing...")
        force_camera_release()  # Clean up any existing camera instance

        # Platform detection for camera backend
        if sys.platform == "win32":
            camera_backends = [
                lambda: cv2.VideoCapture(0, cv2.CAP_DSHOW),
                lambda: cv2.VideoCapture(0)
            ]
        else:
            camera_backends = [
                lambda: cv2.VideoCapture(0, cv2.CAP_ANY),
                lambda: cv2.VideoCapture(0)
            ]

        # Try different camera initialization methods
        for camera_init in camera_backends:
            try:
                cam = camera_init()
                time.sleep(0.3)  # Give camera time to initialize
                if cam and cam.isOpened():
                    with _state_lock:
                        camera = cam
                    break
            except Exception as e:
                logger.warning(f"Camera init method failed: {str(e)}")

        # Verify camera is working
        with _state_lock:
            cam = camera
        if cam is None or not cam.isOpened():
            raise Exception(
                "Could not open camera. Please make sure your camera is connected and not being used by another application.")

        # Try to get a test frame
        ret, test_frame = cam.read()
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
                cam.set(prop, value)
            except Exception:
                pass  # Continue if one property can't be set

        # Add a starting frame to queue
        signal_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.putText(signal_frame, "Camera Started", (90, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        try:
            frame_queue.put_nowait(signal_frame)
        except queue.Full:
            _drain_queue()
            frame_queue.put_nowait(signal_frame)

        # Initialize MediaPipe with performance options
        with mp_hands.Hands(
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
            max_num_hands=1,
            model_complexity=0
        ) as hands:
            # Update status
            with _state_lock:
                gesture_status["message"] = "Camera ready - show gestures"

            # Processing variables
            skip_frames, frame_counter = 1, 0
            prev_frame_time = time.time()

            # Main processing loop
            while True:
                # Check loop condition under lock
                with _state_lock:
                    if not is_recognition_active or success or attempts <= 0 or camera is None:
                        break

                # Check camera
                if not cam.isOpened():
                    with _state_lock:
                        gesture_status.update(
                            {"status": "error", "message": "Camera error: Camera was closed unexpectedly"})
                    break

                ret, frame = cam.read()
                if not ret or frame is None or frame.size == 0:
                    with _state_lock:
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

                        # Read gesture_sequence under lock for overlay
                        with _state_lock:
                            seq_snapshot = list(gesture_sequence)

                        # Add text overlays
                        for idx, text in [
                            ("Processing: Active", 30),
                            (f"Gestures: {', '.join(seq_snapshot) if seq_snapshot else 'None'}", 60),
                            (f"FPS: {round(fps, 1)}", 90)
                        ]:
                            cv2.putText(output_frame, text, (85, idx),
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
                                with _state_lock:
                                    if current_gesture and current_gesture != last_gesture:
                                        gesture_sequence.append(current_gesture)
                                        gesture_status["message"] = f"{current_gesture.capitalize()} Gesture Detected"
                                        last_gesture = current_gesture

                                        # Display detected gesture
                                        gesture_indicator = f"DETECTED: {current_gesture.upper()}"
                                        text_size = cv2.getTextSize(
                                            gesture_indicator, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                                        text_x = (
                                            output_frame.shape[1] - text_size[0]) // 2
                                        cv2.putText(output_frame, gesture_indicator, (text_x, 20),
                                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

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
                        with _state_lock:
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

                try:
                    frame_queue.put_nowait(output_frame)
                except queue.Full:
                    # Drop oldest frame to make room
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        frame_queue.put_nowait(output_frame)
                    except queue.Full:
                        pass

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in process_gestures: {error_msg}")
        with _state_lock:
            camera_error = True
            gesture_status.update(
                {"status": "error", "message": f"Error accessing camera: {error_msg}"})
    finally:
        release_camera()
        with _state_lock:
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
            with _state_lock:
                active = is_recognition_active
            if not active:
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
    with _state_lock:
        return jsonify(dict(gesture_status))


@app.route('/start_recognition', methods=['POST'])
def start_recognition():
    global is_recognition_active, gesture_thread

    with _state_lock:
        active = is_recognition_active
        thread = gesture_thread

    # Ensure previous resources are cleaned up
    if thread and thread.is_alive():
        logger.info("Previous gesture thread still running, stopping it first")
        with _state_lock:
            is_recognition_active = False
        try:
            thread.join(timeout=2.0)
        except Exception as e:
            logger.warning(f"Error joining previous thread: {str(e)}")

    force_camera_release()

    # Start recognition
    try:
        reset_recognition()
        with _state_lock:
            is_recognition_active = True
            gesture_status["message"] = "Initializing camera..."

        new_thread = threading.Thread(target=process_gestures)
        new_thread.daemon = True
        new_thread.start()
        with _state_lock:
            gesture_thread = new_thread

        time.sleep(0.5)  # Brief wait for camera initialization
        logger.info("Recognition thread started")
        return jsonify({"status": "success", "message": "Recognition started"})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error starting recognition: {error_msg}")
        with _state_lock:
            is_recognition_active = False
            gesture_status.update(
                {"status": "error", "message": f"Error starting recognition: {error_msg}"})
        return jsonify({"status": "error", "message": f"Failed to start recognition: {error_msg}"})


@app.route('/stop_recognition', methods=['POST'])
def stop_recognition():
    global is_recognition_active, gesture_thread
    with _state_lock:
        active = is_recognition_active
        thread = gesture_thread

    if active:
        with _state_lock:
            is_recognition_active = False
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        _drain_queue()
        release_camera()
        reset_recognition()
        return jsonify({"status": "success", "message": "Recognition stopped"})
    return jsonify({"status": "error", "message": "Recognition not running"})


@app.teardown_appcontext
def cleanup(error):
    if error is not None:
        logger.info(f"Application context teardown with error: {error}")
        global is_recognition_active, gesture_thread
        with _state_lock:
            is_recognition_active = False
            thread = gesture_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        force_camera_release()


def _shutdown_cleanup():
    """Cleanup handler for process exit."""
    global is_recognition_active, gesture_thread
    logger.info("Process exiting — cleaning up resources")
    with _state_lock:
        is_recognition_active = False
        thread = gesture_thread
    if thread and thread.is_alive():
        thread.join(timeout=3.0)
    _drain_queue()
    release_camera()
    cv2.destroyAllWindows()


atexit.register(_shutdown_cleanup)


if __name__ == '__main__':
    try:
        logger.info("Starting HandWave Unlock application...")
        force_camera_release()  # Force cleanup at start
        app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        cleanup(e)
        sys.exit(1)
