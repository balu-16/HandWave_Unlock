// Function to toggle troubleshooting section
function toggleTroubleshooting() {
    const troubleshootingSection = document.getElementById('troubleshooting');
    const troubleshootBtn = document.getElementById('troubleshootBtn');
    
    if (troubleshootingSection.classList.contains('active')) {
        troubleshootingSection.classList.remove('active');
        troubleshootBtn.textContent = 'Camera Troubleshooting ▼';
    } else {
        troubleshootingSection.classList.add('active');
        troubleshootBtn.textContent = 'Camera Troubleshooting ▲';
    }
}

// Function to update status message
function updateStatus() {
    fetch('/gesture_status')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('status');
            statusElement.textContent = data.message;
            statusElement.className = `status ${data.status}`;
            
            // If recognition has stopped, enable start button and disable stop button
            if (data.message.includes("Click 'Start Recognition'") || 
                data.status === "error" || 
                data.status === "success") {
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                
                // If there was a camera error, show it more prominently and auto-open troubleshooting
                if (data.status === "error" && (
                    data.message.includes("Error accessing camera") || 
                    data.message.includes("Camera connection") ||
                    data.message.includes("Camera is being used")
                )) {
                    const videoContainer = document.getElementById('video-container');
                    videoContainer.innerHTML = `<div class="error">${data.message}<br><br>See troubleshooting tips below.</div>`;
                    videoContainer.classList.remove('active');
                    
                    // Auto-open the troubleshooting section
                    const troubleshootingSection = document.getElementById('troubleshooting');
                    const troubleshootBtn = document.getElementById('troubleshootBtn');
                    if (!troubleshootingSection.classList.contains('active')) {
                        troubleshootingSection.classList.add('active');
                        troubleshootBtn.textContent = 'Camera Troubleshooting ▲';
                    }
                }
            }
        })
        .catch(error => console.error('Error fetching status:', error));
}

// Function to handle start recognition
function startRecognition() {
    console.log("Start button clicked");
    
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const videoContainer = document.getElementById('video-container');
    
    // Prevent double-clicks
    if (startBtn.disabled) {
        console.log("Button already disabled, ignoring click");
        return;
    }
    
    // Update UI immediately to provide feedback
    startBtn.disabled = true;
    stopBtn.disabled = true; // Keep disabled until camera is confirmed working
    
    // Show loading message
    const loadingElement = document.createElement('div');
    loadingElement.className = 'loading';
    loadingElement.textContent = 'Starting camera...';
    
    // Clear video container and add loading message
    videoContainer.innerHTML = '';
    videoContainer.appendChild(loadingElement);
    
    console.log("Sending start_recognition request...");
    
    // Add a timeout to handle long-running requests
    const timeoutId = setTimeout(() => {
        console.log("Request timeout - server taking too long to respond");
        
        // Inform user of timeout
        videoContainer.innerHTML = '';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.innerHTML = 'Server taking too long to respond.<br><br>Check if your camera is connected and not in use by another application.';
        videoContainer.appendChild(errorDiv);
        
        // Reset button states
        startBtn.disabled = false;
        stopBtn.disabled = true;
        
        // Auto-open troubleshooting
        const troubleshootingSection = document.getElementById('troubleshooting');
        if (!troubleshootingSection.classList.contains('active')) {
            toggleTroubleshooting();
        }
    }, 15000); // 15 second timeout
    
    // Call the backend to start recognition
    fetch('/start_recognition', {
        method: 'POST',
        headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
    })
    .then(response => {
        // Clear timeout as we got a response
        clearTimeout(timeoutId);
        console.log("Received response from start_recognition");
        return response.json();
    })
    .then(data => {
        console.log("Start recognition response:", data);
        
        if (data.status === 'success') {
            // Enable stop button now that we know recognition started
            stopBtn.disabled = false;
            
            // Clear the loading message
            videoContainer.innerHTML = '';
            
            // Create and add the video feed
            const videoFeed = document.createElement('img');
            videoFeed.id = 'video-feed';
            videoFeed.src = `/video_feed?t=${new Date().getTime()}`; // Add timestamp to prevent caching
            
            // Add loading class until image loads
            videoContainer.classList.add('active');
            
            // Handle video feed load error with detailed error messaging
            videoFeed.onerror = function(e) {
                console.error("Error loading video feed:", e);
                
                // Create error message with troubleshooting tips
                videoContainer.innerHTML = `
                    <div class="error">
                        Failed to load camera feed<br><br>
                        <strong>Troubleshooting tips:</strong><br>
                        1. Check camera connection<br>
                        2. Close other applications using camera<br>
                        3. Refresh page and try again<br>
                        4. Restart your computer
                    </div>
                `;
                
                // Reset button states
                startBtn.disabled = false;
                stopBtn.disabled = true;
                
                // Auto-open troubleshooting
                const troubleshootingSection = document.getElementById('troubleshooting');
                if (!troubleshootingSection.classList.contains('active')) {
                    toggleTroubleshooting();
                }
                
                // Stop recognition on the server since video feed failed
                stopRecognition(false); // Don't update UI
            };
            
            // When video feed loads successfully
            videoFeed.onload = function() {
                console.log("Video feed loaded successfully");
                // Remove any existing loading elements
                const loadingElements = videoContainer.querySelectorAll('.loading');
                loadingElements.forEach(el => el.remove());
            };
            
            // Add video feed to container
            videoContainer.appendChild(videoFeed);
            
        } else {
            console.error("Failed to start recognition:", data.message);
            
            // Update UI to show error with troubleshooting steps
            videoContainer.innerHTML = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.innerHTML = `
                ${data.message || 'Failed to start camera'}<br><br>
                <strong>See troubleshooting section below for solutions.</strong>
            `;
            videoContainer.appendChild(errorDiv);
            
            // Auto-open troubleshooting
            const troubleshootingSection = document.getElementById('troubleshooting');
            if (!troubleshootingSection.classList.contains('active')) {
                toggleTroubleshooting();
            }
            
            // Reset button states
            startBtn.disabled = false;
            stopBtn.disabled = true;
            videoContainer.classList.remove('active');
        }
    })
    .catch(error => {
        // Clear timeout as we got a response (even if it's an error)
        clearTimeout(timeoutId);
        console.error("Error starting recognition:", error);
        
        // Update UI to show error
        videoContainer.innerHTML = '';
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.innerHTML = `
            Network error when starting recognition<br><br>
            <strong>Possible solutions:</strong><br>
            1. Check your internet connection<br>
            2. Refresh the page<br>
            3. Restart your browser
        `;
        videoContainer.appendChild(errorDiv);
        
        // Reset button states
        startBtn.disabled = false;
        stopBtn.disabled = true;
        videoContainer.classList.remove('active');
    });
}

// Function to handle stop recognition
function stopRecognition(updateUI = true) {
    console.log("Stop button clicked");
    
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const videoContainer = document.getElementById('video-container');
    
    // Update UI immediately if requested
    if (updateUI) {
        startBtn.disabled = true;
        stopBtn.disabled = true;
        videoContainer.classList.remove('active');
    }

    // Call the backend to stop recognition
    fetch('/stop_recognition', {
        method: 'POST',
        headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log("Stop recognition response:", data);
        
        // Enable start button again
        startBtn.disabled = false;
        
        // Reset video container if UI update requested
        if (updateUI) {
            videoContainer.innerHTML = '';
            
            // Add waiting message
            const waitingDiv = document.createElement('div');
            waitingDiv.className = 'waiting';
            waitingDiv.textContent = 'Camera stopped. Click Start Recognition to begin.';
            videoContainer.appendChild(waitingDiv);
        }
    })
    .catch(error => {
        console.error("Error stopping recognition:", error);
        startBtn.disabled = false;
        
        // Add error message if UI update requested
        if (updateUI) {
            videoContainer.innerHTML = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = 'Error stopping recognition';
            videoContainer.appendChild(errorDiv);
        }
    });
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM fully loaded");
    
    // Set up status updates
    setInterval(updateStatus, 1000);
    
    // Set up video container with waiting message
    const videoContainer = document.getElementById('video-container');
    videoContainer.innerHTML = '';
    const waitingDiv = document.createElement('div');
    waitingDiv.className = 'waiting';
    waitingDiv.textContent = 'Click Start Recognition to begin';
    videoContainer.appendChild(waitingDiv);
    
    // Set up button click handlers
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const troubleshootBtn = document.getElementById('troubleshootBtn');
    
    if (startBtn) {
        startBtn.addEventListener('click', function() {
            startRecognition();
        });
    } else {
        console.error('Start button not found in DOM');
    }
    
    if (stopBtn) {
        stopBtn.addEventListener('click', function() {
            stopRecognition();
        });
    } else {
        console.error('Stop button not found in DOM');
    }
    
    if (troubleshootBtn) {
        troubleshootBtn.addEventListener('click', toggleTroubleshooting);
    } else {
        console.error('Troubleshoot button not found in DOM');
    }
    
    // Add keyboard shortcut for stopping recognition (Esc key)
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && !stopBtn.disabled) {
            console.log('Escape key pressed, stopping recognition');
            stopRecognition();
        }
    });

    // Smooth scroll for gesture guide
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
    
    // Keep track of disconnection
    window.addEventListener('online', function() {
        console.log('Browser now online');
        updateStatus();
    });
    
    window.addEventListener('offline', function() {
        console.log('Browser now offline');
        const statusElement = document.getElementById('status');
        statusElement.textContent = 'Network disconnected';
        statusElement.className = 'status error';
    });
    
    // Handle browser visibility changes
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            console.log('Page is now visible - updating status');
            updateStatus();
        }
    });
    
    console.log("Application initialized");
}); 