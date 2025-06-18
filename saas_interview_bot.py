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

            logger.info("SaaSInterviewBot initialized successfully")

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            # Provide user feedback in GUI if possible, otherwise print
            if hasattr(self, 'status_label') and self.status_label:
                 self._update_status(f"Initialization failed: {e}", "red")
            else:
                 print(f"Initialization failed: {e}")
            raise
