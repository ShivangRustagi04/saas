import os
import re
import random
import time
import queue
import threading
import logging
import subprocess
import sys
import pygame
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
from dotenv import load_dotenv
import cv2
import numpy as np
import pygetwindow as gw
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk
import base64
import boto3
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SaaSInterviewBot:
    def __init__(self, model="gemini-2.0-flash", accent="us"):
        try:
            # Initialize all attributes first
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("Please set the GEMINI_API_KEY in .env file")

            # Core AI setup
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model)

            # Interview state management
            self.interview_state = "introduction"
            self.conversation_history = []
            self.last_question = None

            # Audio setup
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.recognizer.pause_threshold = 0.6
            self.recognizer.phrase_threshold = 0.2

            # Monitoring flags
            self.is_listening = False
            self.interrupted = False
            self.tone_warnings = 0
            self.cheating_warnings = 0
            self.tab_monitor_ready = False
            self.last_face_detection_time = time.time()
            self.tab_change_detected = False
            self.interview_active = True
            self.monitoring_active = True

            # Configuration
            self.response_delay = 0.3
            self.accent = accent.lower()

            # Thread safety
            self._lock = threading.Lock()
            self._frame_counter = 0

            # Initialize face detection
            try:
                self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            except Exception as e:
                logger.warning(f"Face detection initialization failed: {e}")
                self.face_cascade = None
                self.eye_cascade = None

            # Initialize camera
            self.cap = None
            self.camera_active = False

            # Initialize local TTS engine
            try:
                self.local_tts = pyttsx3.init()
                self._configure_tts_engine()
            except Exception as e:
                logger.error(f"TTS initialization failed: {e}")
                self.local_tts = None

            # GUI components
            self.root = None
            self.camera_label = None
            self.status_label = None

            # TTS queue and thread
            self.tts_queue = queue.Queue(maxsize=10)
            self.tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
            self.tts_thread.start()
            # ✅ Amazon Polly Initialization
            try:
                self.polly = boto3.client(
                    "polly",
                    region_name=os.getenv("AWS_REGION", "ap-south-1"),
                    aws_access_key_id=os.getenv("AKIATFBMPLHYKFLISU5W"),
                    aws_secret_access_key=os.getenv("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")
                )
                logger.info("✅ Amazon Polly initialized successfully")
            except Exception as e:
                logger.warning(f"❌ Polly initialization failed: {e}")
                raise
        except Exception as e:
            logger.error(f"Initialization error in SaaSInterviewBot: {e}")
            raise


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        """Comprehensive cleanup of all resources"""
        logger.info("Starting cleanup process...")

        with self._lock:
            self.interview_active = False
            self.monitoring_active = False

        # Stop TTS thread
        try:
            self.tts_queue.put(None, timeout=1)
            if hasattr(self, 'tts_thread') and self.tts_thread.is_alive():
                self.tts_thread.join(timeout=2)
        except:
            pass

        # Stop monitoring threads
        for thread_name in ['face_monitor_thread', 'tab_monitor_thread']:#
            if hasattr(self, thread_name):
                thread = getattr(self, thread_name)
                if thread.is_alive():
                    thread.join(timeout=2)

        # Clean up camera
        self._stop_camera()

        # Clean up audio
        try:
            if self.local_tts:
                self.local_tts.stop()
            # Pygame mixer might not be initialized if audio failed
            if pygame.mixer.get_init():
                 pygame.mixer.quit()
        except Exception as e:
            logger.error(f"Audio cleanup error: {e}")


        logger.info("Cleanup completed")

    def wait_after_speaking(self, message, base=1.5, per_word=0.35):
        if not message:
            time.sleep(base + 2)
            return
        words = message.split()
        delay = base + per_word * len(words)
        print(f"[Pause] Waiting {round(delay, 1)}s after speaking.")
        time.sleep(delay)

    def _tts_loop(self):
        """Thread function to handle TTS queue"""
        while True:
            try:
                text = self.tts_queue.get(timeout=1)
                if text is None:
                    break

                if self.local_tts and not self.interrupted:
                    self.local_tts.say(text)
                    self.local_tts.runAndWait()

                self.tts_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS error: {e}")
                continue

    def _configure_tts_engine(self):
        """Configure TTS engine based on selected accent"""
        if not self.local_tts:
            return

        try:
            voices = self.local_tts.getProperty('voices')

            if self.accent == "indian":
                # Try to find an Indian English voice
                for voice in voices:
                    if "india" in voice.name.lower():
                        self.local_tts.setProperty('voice', voice.id)
                        break
                else:
                    # Fallback to any English voice
                    for voice in voices:
                        if "english" in voice.name.lower():
                            self.local_tts.setProperty('voice', voice.id)
                            break
            elif self.accent == "us":
                # Try to find a US English voice
                for voice in voices:
                    if "us" in voice.name.lower() or "american" in voice.name.lower():
                        self.local_tts.setProperty('voice', voice.id)
                        break

            # Common settings
            self.local_tts.setProperty('rate', 160)
            self.local_tts.setProperty('volume', 1.0)

        except Exception as e:
            logger.error(f"TTS configuration error: {e}")

        def speak(self, text, interruptible=True):
            """Speak text using Amazon Polly and emit audio to frontend"""
            if self.interrupted and interruptible:
                self.interrupted = False
                return

            print(f"Interviewer (Polly): {text}")

            try:
        # Setup Polly client if not already done
                if not hasattr(self, "polly"):
                    self.polly = boto3.client(
                        "polly",
                        region_name="ap-south-1",  # or any preferred region
                        aws_access_key_id=os.getenv("AKIATFBMPLHYKFLISU5W"),
                        aws_secret_access_key=os.getenv("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")
                    )

                response = self.polly.synthesize_speech(
                    Text=text,
                    OutputFormat="mp3",
                    VoiceId="Aditi"  # or "Joanna", "Kendra", etc.
                )

                audio_bytes = response["AudioStream"].read()
                base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                from flask_socketio import SocketIO
                from flask import current_app

        # Emit both text and audio
                socketio = current_app.extensions['socketio']
                socketio.emit("ai_response", {
                    "message": text,
                    "audio": base64_audio,
                    "timestamp": time.time()
                })

            except Exception as e:
                print(f"Polly error: {e}")
        # Fallback to just sending text
            try:
                socketio.emit("ai_message", {
                    "message": text,
                    "timestamp": time.time()
                })
            except:
                pass

    def listen(self, max_attempts=3, timeout=15):
        """Listen for user response with improved error handling"""
        for attempt in range(max_attempts):
            try:
                with self.microphone as source:
                    print(f"\nListening... (Attempt {attempt + 1}/{max_attempts})")

                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                    # Listen for audio
                    audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=60)

                    # Recognize speech
                    text = self.recognizer.recognize_google(audio)
                    print(f"Candidate: {text}")

                    # Validate response
                    if not text.strip():
                        continue

                    # Check tone
                    tone = self._detect_tone(text)
                    if tone != "professional":
                        self.handle_improper_tone(tone)
                        # Don't skip the response, just warn

                    return text.strip()

            except sr.WaitTimeoutError:
                if attempt < max_attempts - 1:
                    self.speak("I didn't hear anything. Please speak when you're ready.", interruptible=True)
                    time.sleep(2)
                continue

            except sr.UnknownValueError:
                if attempt < max_attempts - 1:
                    self.speak("I couldn't quite catch that. Could you please repeat?", interruptible=True)
                    time.sleep(2)
                continue

            except sr.RequestError as e:
                logger.error(f"Speech recognition error: {e}")
                if attempt < max_attempts - 1:
                    self.speak("There was a technical issue. Please try speaking again.", interruptible=True)
                    time.sleep(2)
                continue

            except Exception as e:
                logger.error(f"Unexpected error in listen(): {e}")
                break

        # If all attempts fail, return placeholder
        self.speak("Let's continue with the next part of our interview.", interruptible=True)
        return "[Response unclear after multiple attempts]"

    def _detect_tone(self, text):
        """Detect tone of the candidate's response"""
        if not text:
            return "professional"

        text_lower = re.sub(r'\\s+', ' ', text.lower().strip())

        arrogant_keywords = [
            r'\\bobviously\\b', r'\\beveryone knows\\b', r'\\bchild\\\'?s play\\b',
            r'\\bthat\\\'?s easy\\b', r'\\btrivial\\b', r'\\bwaste of time\\b',
            r'\\bno brainer\\b', r'\\bpiece of cake\\b'
        ]

        rude_patterns = [
            r'\\byou don\\\'?t understand\\b', r'\\bthat\\\'?s stupid\\b', r'\\bdumb question\\b',
            r'\\bare you serious\\b', r'\\bthis is ridiculous\\b', r'\\bwho cares\\b',
            r'\\bwhatever\\b', r'\\bthis sucks\\b'
        ]

        for pattern in arrogant_keywords:
            if re.search(pattern, text_lower):
                return "arrogant"

        for pattern in rude_patterns:
            if re.search(pattern, text_lower):
                return "rude"

        return "professional"

    def handle_improper_tone(self, tone):
        """Handle inappropriate tone from candidate"""
        self.tone_warnings += 1

        if self.tone_warnings >= 3:
            self.speak("I appreciate your participation, but let's maintain a professional tone throughout our conversation.", interruptible=True)
            self._update_status("Professional communication required", "orange")
            return

        responses = {
            "arrogant": [
                "I appreciate your confidence! Let's channel that into demonstrating your sales knowledge.",
                "Great confidence! Now let's see how you apply that expertise to sales scenarios.",
            ],
            "rude": [
                "I understand interviews can be stressful. Let's take a moment and continue professionally.",
                "No worries, let's refocus on showcasing your sales abilities.",
            ]
        }

        if tone in responses:
            response = random.choice(responses[tone])
            self.speak(response, interruptible=True)
            time.sleep(1)


    def query_gemini(self, prompt, max_retries=3):
        """Query Gemini AI with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)

                if hasattr(response, 'text') and response.text:
                    return response.text
                elif hasattr(response, 'candidates') and response.candidates:
                    return response.candidates[0].content.parts[0].text
                else:
                    logger.warning(f"Unexpected response format from Gemini: {response}")

            except Exception as e:
                logger.error(f"Gemini API Error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief pause before retry
                continue

        # Fallback responses
        fallbacks = [
            "Could you tell me more about your experience with that?",
            "That's interesting. Can you elaborate on your approach?",
            "What challenges have you faced in that area?",
            "Tell me more about your sales process."
        ]
        return random.choice(fallbacks)

    def _setup_gui(self):
        """Setup full-screen video feed with footer warning/status"""
        try:
            self.root = tk.Tk()
            self.root.title("SaaS Sales Interview - AI Interviewer")
            self.root.geometry("1024x768")
            self.root.configure(bg='#2c3e50')

        # Make the window stay on top initially
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(1000, lambda: self.root.attributes('-topmost', False))
            self.root.focus_force()

        # Configure grid layout (1 row for video, 1 row for footer)
            self.root.grid_rowconfigure(0, weight=9)  # Camera area
            self.root.grid_rowconfigure(1, weight=1)  # Footer
            self.root.grid_columnconfigure(0, weight=1)

        # === Video Frame ===
            video_frame = ttk.Frame(self.root)
            video_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

            self.camera_label = ttk.Label(video_frame, text="Loading camera feed...", anchor='center')
            self.camera_label.pack(fill=tk.BOTH, expand=True)

        # === Footer Frame ===
            footer_frame = ttk.Frame(self.root)
            footer_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

            self.status_label = ttk.Label(
                footer_frame,
                text="Status: Interview Ready",
                foreground="green",
                font=("Arial", 12, "bold")
            )
            self.status_label.pack(side=tk.LEFT)

            self.warning_label = ttk.Label(
                footer_frame,
                text="⚠️ Ensure good lighting, clear audio, and stable internet.",
                font=("Arial", 10),
                foreground="orange"
            )
            self.warning_label.pack(side=tk.RIGHT)

        # Start camera
            self._start_camera()
            self._update_camera_feed()

            logger.info("GUI setup completed")

        except Exception as e:
            logger.error(f"GUI setup error: {e}")
            raise


    def _start_camera(self):
        """Start camera for monitoring"""
        try:
            if not self.camera_active:
                self.cap = cv2.VideoCapture(0)
                if self.cap is not None and self.cap.isOpened():
                    self.camera_active = True
                    logger.info("Camera started successfully")
                else:
                    logger.warning("Failed to open camera")
                    # Show a message box to the user
                    if self.root:
                        messagebox.showerror("Camera Error", "Could not access the camera. Please ensure it is connected and not in use by another application.")
        except Exception as e:
            logger.error(f"Camera start error: {e}")
            if self.root:
                messagebox.showerror("Camera Error", f"An error occurred while starting the camera: {e}")


    def _stop_camera(self):
        """Stop the camera"""
        try:
            if self.camera_active and self.cap:
                self.cap.release()
                self.camera_active = False
                if self.camera_label:
                    self.camera_label.configure(image='', text="Camera Off")
                logger.info("Camera stopped")
        except Exception as e:
            logger.error(f"Camera stop error: {e}")

    def _update_camera_feed(self):
        """Update camera feed in GUI with optimization"""
        if not self.camera_active or not self.cap or not self.cap.isOpened():
            if self.root and self.interview_active:
                # Try to restart camera if it failed
                self._start_camera()
                self.root.after(1000, self._update_camera_feed) # Retry after 1 sec
            return

        # Frame skipping for optimization
        self._frame_counter += 1
        if self._frame_counter % 3 != 0:  # Process every third frame
            if self.root and self.camera_active:
                self.root.after(50, self._update_camera_feed)
            return

        try:
            ret, frame = self.cap.read()
            if ret and self.camera_label:
                # Resize and convert frame
                frame = cv2.resize(frame, (640, 480)) # Increased size for better visibility
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Draw bounding boxes if face detection is active and faces are found
                if self.face_cascade and self.monitoring_active:
                     gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                     faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                     for (x,y,w,h) in faces:
                         cv2.rectangle(frame_rgb, (x,y), (x+w,y+h), (255,0,0), 2) # Blue rectangle for face


                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=img)

                # Update display
                self.camera_label.configure(image=photo, text='')
                self.camera_label.image = photo # Keep a reference

        except Exception as e:
            logger.error(f"Camera feed update error: {e}")

        # Schedule next update
        if self.root and self.camera_active and self.interview_active:
            self.root.after(50, self._update_camera_feed)

    def _monitor_face_and_attention(self):
        """Monitor face detection and attention"""
        if not self.face_cascade or not self.eye_cascade:
            logger.warning("Face detection not available for monitoring.")
            return

        last_face_time = time.time()
        no_face_warning_given = False
        multiple_faces_warning_given = False

        while self.monitoring_active and self.interview_active:
            try:
                if not self.camera_active or not self.cap or not self.cap.isOpened():
                    time.sleep(1)
                    continue

                ret, frame = self.cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

                # Check face count
                if len(faces) == 0:
                    if time.time() - last_face_time > 20 and not no_face_warning_given:
                        self._handle_cheating_attempt("no_face")
                        no_face_warning_given = True
                else:
                    last_face_time = time.time()
                    no_face_warning_given = False

                    if len(faces) > 1 and not multiple_faces_warning_given:
                        self._handle_cheating_attempt("multiple_faces")
                        multiple_faces_warning_given = True
                    elif len(faces) == 1:
                        multiple_faces_warning_given = False

                time.sleep(1) # Check every second

            except Exception as e:
                logger.error(f"Face monitoring error: {e}")
                time.sleep(2)


    def _monitor_tab_changes(self):
        """Monitor for tab/window changes"""
        while not self.tab_monitor_ready:
            time.sleep(0.5)

        try:
            initial_window = gw.getActiveWindow()
        except Exception as e:
            initial_window = None
            logger.warning(f"Window monitoring not available: {e}")
            return

        while self.monitoring_active and self.interview_active:
            try:
                current_window = gw.getActiveWindow()

                if initial_window and current_window:
                    if (current_window.title != initial_window.title and
                        not self.tab_change_detected):
                        self.tab_change_detected = True
                        self._handle_cheating_attempt("tab_change")
                        time.sleep(5) # Cooldown period
                    else:
                        self.tab_change_detected = False

            except Exception as e:
                logger.error(f"Tab monitoring error: {e}")

            time.sleep(3) # Check every 3 seconds

    def _handle_cheating_attempt(self, cheat_type):
        """Handle cheating attempts with graduated response"""
        with self._lock:
            self.cheating_warnings += 1

        if self.cheating_warnings >= 3:
            self.speak("Multiple policy violations detected. This interview session will now end.", interruptible=False)
            self._update_status("Interview terminated - Policy violations", "red")
            self.interview_active = False
            return

        responses = {
            "no_face": "Please ensure your face is clearly visible to the camera throughout the interview.",
            "multiple_faces": "Please ensure you are alone during this interview session.",
            "looking_away": "Please maintain focus on the interview and avoid looking at other devices.",
            "tab_change": "Please stay focused on the interview and avoid switching to other applications."
        }

        if cheat_type in responses:
            warning_msg = f"Reminder: {responses[cheat_type]} This is warning {self.cheating_warnings} of 3."
            self.speak(warning_msg, interruptible=False)
            self._update_status(f"Warning {self.cheating_warnings}/3: {cheat_type.replace('_', ' ').title()}", "orange")


    def _update_status(self, message, color="green"):
        """Update status display"""
        if self.status_label:
            self.status_label.configure(text=f"Status: {message}", foreground=color)
            if self.root:
                self.root.update_idletasks()


    def _conclude_interview(self):
        """Gracefully conclude the interview"""
        if self.interview_active:
            self._update_status("Interview concluding", "green")
            self.speak("That was a great conversation. Thank you for sharing your insights.", interruptible=True)
            time.sleep(1)

            self.speak("Do you have any questions for me about the role, the company, or the next steps?", interruptible=True)
            time.sleep(6) # Give time for candidate to think and respond
            final_questions = self.listen()

            if final_questions and "[Response unclear" not in final_questions:
                self.conversation_history.append({"role": "user", "content": final_questions})
                self.speak("Those are great questions! The hiring team will be in touch with more details on the next steps very soon.", interruptible=True)
                time.sleep(1)
            else:
                 self.speak("Okay, if you don't have any questions right now, that's perfectly fine.", interruptible=True)
                 time.sleep(1)


            self.speak("Thank you so much for your time today. It was a pleasure speaking with you, and I wish you the best of luck!", interruptible=True)
            self._update_status("Interview completed successfully!", "green")

        else:
             # Interview ended prematurely due to violations or errors
             pass # Message already spoken in _handle_cheating_attempt or main error handling


        self.interview_active = False # Ensure interview active flag is false
        self.monitoring_active = False # Stop monitoring threads

        # Close the GUI after a delay
        if self.root:
            self.root.after(5000, self.root.quit)


    def _run_interview_logic(self):
        """Main interview logic for SaaS Sales"""
        try:
            self._update_status("Interview starting...", "blue")

            # --- Introduction Phase ---
            self.speak("Hello! I'm Gyani, your AI interviewer for this SaaS Sales role. Welcome to the interview!", interruptible=True)
            self.wait_after_speaking("Hello! I'm Gyani, your AI interviewer for this SaaS Sales role. Welcome to the interview!")

            self.speak("Before we dive into the sales questions, how has your day been so far?", interruptible=True)
            self.wait_after_speaking("Before we dive into the sales questions, how has your day been so far?")
            day_response = self.listen()
            if day_response and "[Response unclear" not in day_response:
                self.conversation_history.append({"role": "user", "content": day_response})
                self.speak("That's great to hear! I appreciate you taking the time for this interview.", interruptible=True)
                time.sleep(1)

            self.speak("To start, could you please introduce yourself and tell me a bit about your background in sales, particularly any experience with SaaS products?", interruptible=True)
            self.wait_after_speaking("To start, could you please introduce yourself and tell me a bit about your background in sales, particularly any experience with SaaS products?")
            introduction = self.listen()
            if introduction and "[Response unclear" not in introduction and len(introduction.split()) > 5:
                self.conversation_history.append({"role": "user", "content": introduction})
                self.speak("Thank you for that introduction. It's great to hear about your experience.", interruptible=True)
                time.sleep(1)
            else:
                 self.speak("Okay, thank you.", interruptible=True)
                 time.sleep(1)

            # Ensure camera and monitoring are active before proceeding
            if not self.camera_active:
                self._start_camera()
                self._update_camera_feed()

            # Start monitoring threads if not already started
            if not hasattr(self, 'face_monitor_thread') or not self.face_monitor_thread.is_alive():
                 self.face_monitor_thread = threading.Thread(target=self._monitor_face_and_attention)
                 self.face_monitor_thread.daemon = True
                 self.face_monitor_thread.start()

            if not hasattr(self, 'tab_monitor_thread') or not self.tab_monitor_thread.is_alive():
                 self.tab_monitor_thread = threading.Thread(target=self._monitor_tab_changes)
                 self.tab_monitor_thread.daemon = True
                 self.tab_monitor_thread.start()


            self._update_status("Sales discussion phase", "green")
            # --- Sales Questions Phase ---
            question_count = 0
            max_questions = 7 # Adjusted number of questions for sales focus

            while question_count < max_questions and self.interview_active:
                if len(self.conversation_history) > 15:
                    # Keep conversation history manageable for the AI
                    self.conversation_history = self.conversation_history[-8:]

                system_prompt = f"""As a friendly and professional SaaS sales interviewer, ask one engaging question based on this conversation context.
The question should:
- Be encouraging and conversational
- Build on what the candidate has shared about their sales background
- Test practical SaaS sales knowledge and experience (e.g., sales process, lead qualification, understanding needs, presenting value, handling objections, closing, CRM tools, relationship building)
- Be appropriate for a sales professional
- Keep it to one clear question
- Focus on real-world SaaS sales scenarios
- Avoid repeating previous questions or asking basic technical questions
- Question should be concise

Recent conversation: {' '.join([msg['content'] for msg in self.conversation_history[-4:]])}

Generate only the question in a friendly, professional tone."""

                response = self.query_gemini(system_prompt)

                if response and response.strip() != self.last_question:
                    msg = response.strip()
                    self.last_question = msg
                    self.speak(msg)
                    self.wait_after_speaking(msg)

                    answer = self.listen()

                    if answer and "[Response unclear" not in answer and len(answer.split()) > 3:
                        self.conversation_history.append({"role": "user", "content": answer})
                        self.conversation_history.append({"role": "assistant", "content": msg})

                        feedback = random.choice([
                            "That's a solid approach!",
                            "Great insight!",
                            "I understand your strategy there.",
                            "That makes sense for that kind of scenario.",
                            "Good explanation of your process."
                        ])
                        self.speak(feedback, interruptible=True)
                        time.sleep(1)
                        question_count += 1

                    if self.root:
                        self.root.update()

                time.sleep(0.5)

            # --- Conclude Interview ---
            self._conclude_interview()

        except Exception as e:
            logger.error(f"Interview logic error: {e}")
            self.speak("We've encountered a technical issue, and the interview will now end. Thank you for your time today!", interruptible=False)
            self._update_status("Interview ended due to technical issue", "red")
            self.interview_active = False
            self.monitoring_active = False
            if self.root:
                 self.root.after(5000, self.root.quit)


    def start_interview(self):
        """Start the GUI and interview process"""
        try:
            self._setup_gui()

            # Start monitoring threads
            self.face_monitor_thread = threading.Thread(target=self._monitor_face_and_attention)
            self.face_monitor_thread.daemon = True
            self.face_monitor_thread.start()

            self.tab_monitor_thread = threading.Thread(target=self._monitor_tab_changes)
            self.tab_monitor_thread.daemon = True
            self.tab_monitor_thread.start()

            # Allow some time for GUI and monitors to initialize before starting interview logic
            self.root.after(1500, lambda: setattr(self, 'tab_monitor_ready', True))
            self.root.after(2000, lambda: threading.Thread(target=self._run_interview_logic, daemon=True).start())


            # Keep GUI active
            self.root.mainloop()

        except Exception as e:
            logger.error(f"Error starting interview: {e}")
            # If GUI failed to set up, cleanup might not happen automatically
            self.cleanup()


if __name__ == "__main__":
    interviewer = None
    try:
        interviewer = SaaSInterviewBot(accent="us") # You can change accent here (e.g., "indian")
        interviewer.start_interview()
    except Exception as e:
        logger.critical(f"Fatal error during interview execution: {e}")
        print("\nInterview session could not start or ended unexpectedly.")
        print("Please check:")
        print("1. Your .env file has GEMINI_API_KEY set correctly.")
        print("2. You have granted microphone and camera permissions.")
        print("3. All required Python packages are installed (check requirements.txt if available).")
        print("4. No other application is using your microphone or camera.")
    finally:
         if interviewer:
             interviewer.cleanup()
         print("\nInterview session ended.")
         print("Thank you for using the AI Interview Bot!")