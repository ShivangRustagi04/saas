from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import queue
import time
import json
import cv2
import base64
import numpy as np
import traceback
import asyncio
from threading import Event
import os

# Try to import your bot, with better error handling
try:
    from hihi import SaaSInterviewBot
    HIHI_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import SaaSInterviewBot from hihi.py: {e}")
    print("Make sure hihi.py is in the same directory and contains the SaaSInterviewBot class")
    HIHI_AVAILABLE = False
    SaaSInterviewBot = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

class WebInterviewBot:
    """Modified version of your SaaSInterviewBot for web interface"""
    def __init__(self):
        self.bot = None
        self.interview_active = False
        self.conversation_history = []
        self.question_count = 0
        self.max_questions = 7
        self.waiting_for_response = False
        self.current_question = None
        self.response_event = threading.Event()
        self.user_response = None
        self.interview_thread = None
        
    def reset_state(self):
        """Reset all interview state - useful for development"""
        print("🔄 Resetting interview state...")
        try:
            # Stop any active interview
            self.interview_active = False
            self.waiting_for_response = False
            
            # Clear response mechanisms
            if hasattr(self, 'response_event'):
                self.response_event.set()  # Unblock any waiting threads
                self.response_event.clear()  # Reset for next use
            
            # Reset interview data    
            self.conversation_history = []
            self.question_count = 0
            self.current_question = None
            self.user_response = None
            
            # Wait for interview thread to finish
            if self.interview_thread and self.interview_thread.is_alive():
                print("⏳ Waiting for interview thread to finish...")
                self.interview_thread.join(timeout=3.0)
                if self.interview_thread.is_alive():
                    print("⚠️ Interview thread didn't finish cleanly")
                else:
                    print("✅ Interview thread finished")
            
            self.interview_thread = None
            
            # Clean up bot if needed
            if self.bot and hasattr(self.bot, 'cleanup'):
                self.bot.cleanup()
                
            # Reset bot instance
            self.bot = None
            
            print("✅ State reset complete")
            return True, "State reset successfully"
            
        except Exception as e:
            error_msg = f"Error resetting state: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())
            return False, error_msg
        
    def initialize_bot(self):
        """Initialize the interview bot"""
        if not HIHI_AVAILABLE:
            return False, "SaaSInterviewBot class not available. Check hihi.py import."
            
        try:
            # Reset state first to ensure clean initialization
            self.reset_state()
            
            # Create bot instance but don't start GUI
            self.bot = SaaSInterviewBot(accent="us")
            # Override the bot's speak method to use websockets instead
            self.bot.speak = self._web_speak
            self.polly = self.bot.polly  # ✅ Pass Polly from the SaaSInterviewBot

            # Override listen method to wait for web input
            self.bot.listen = self._web_listen
            return True, "Bot initialized successfully"
        except Exception as e:
            error_msg = f"Bot initialization error: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            return False, error_msg
    
    def _web_speak(self, text, interruptible=True):
        """Override speak method to send to web interface"""
        print("📢 [BACKEND] _web_speak called with:", text)
        print(f"AI: {text}")
        if hasattr(self, 'polly'):
            print("📞 Calling Amazon Polly for:", text)
            response = self.polly.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId="Aditi"
            )
            audio_bytes = response["AudioStream"].read()
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            print("📦 Polly audio (first 50 chars):", base64_audio[:50])
        else:
            print("❌ Polly not initialized!")
            base64_audio = None


        socketio.emit('ai_response', {
            'message': text,
            'audio': base64_audio,  # ✅ Include Polly voice
            'timestamp': time.time(),
            'interruptible': interruptible
        })

        
        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant", 
            "content": text
        })
        
        # Small delay to allow message to be sent and processed
        time.sleep(1.0)
    
    def _web_listen(self, max_attempts=3, timeout=60):
        """Override listen method to wait for web input"""
        print("🎤 Waiting for user response...")
        
        # Reset the response event and clear previous response
        self.response_event.clear()
        self.user_response = None
        self.waiting_for_response = True
        
        # Notify frontend that we're waiting for response
        socketio.emit('waiting_for_response', {
            'waiting': True,
            'timeout': timeout
        })
        
        # Wait for response with timeout
        response_received = self.response_event.wait(timeout=timeout)
        
        self.waiting_for_response = False
        
        # Notify frontend that we're no longer waiting
        socketio.emit('waiting_for_response', {
            'waiting': False
        })
        
        if response_received and self.user_response:
            print(f"✅ Received user response: {self.user_response}")
            response = self.user_response
            # Clear the response for next time
            self.user_response = None
            return response
        else:
            print("⏰ No response received within timeout")
            return "I didn't receive a response, let's continue with the next question."
    
    def start_interview(self):
        """Start the interview process"""
        if not self.bot:
            return False, "Bot not initialized"
        
        if self.interview_active:
            return False, "Interview already in progress"
        
        try:
            self.interview_active = True
            self.question_count = 0
            self.conversation_history = []
            
            # Start interview in separate thread
            self.interview_thread = threading.Thread(target=self._run_full_interview_logic, daemon=True)
            self.interview_thread.start()
            
            return True, "Interview started successfully"
        except Exception as e:
            error_msg = f"Failed to start interview: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def _run_full_interview_logic(self):
        """Run the complete interview logic from your original bot"""
        try:
            print("🚀 Starting interview logic...")
            
            # Introduction Phase
            socketio.emit('interview_phase', {'phase': 'introduction'})
            
            self.bot.speak("Hello! I'm Gyani, your AI interviewer for this SaaS Sales role. Welcome to the interview!")
            time.sleep(0.5)  # Brief pause
            
            self.bot.speak("Before we dive into the sales questions, how has your day been so far?")
            day_response = self.bot.listen()
            
            if day_response and "didn't receive a response" not in day_response:
                self.conversation_history.append({"role": "user", "content": day_response})
                self.bot.speak("That's great to hear! I appreciate you taking the time for this interview.")
                time.sleep(0.5)

            self.bot.speak("To start, could you please introduce yourself and tell me a bit about your background in sales, particularly any experience with SaaS products?")
            introduction = self.bot.listen()
            
            if introduction and "didn't receive a response" not in introduction and len(introduction.split()) > 3:
                self.conversation_history.append({"role": "user", "content": introduction})
                self.bot.speak("Thank you for that introduction. It's great to hear about your experience.")
                time.sleep(0.5)

            # Sales Questions Phase
            print("🎯 Moving to sales questions phase...")
            socketio.emit('interview_phase', {'phase': 'sales_questions'})
            
            # Sales questions list for fallback
            fallback_questions = [
                "Can you walk me through your typical sales process when approaching a potential SaaS client?",
                "How do you handle objections when a prospect says your SaaS solution is too expensive?",
                "Describe a challenging SaaS deal you closed. What obstacles did you overcome?",
                "How do you identify and qualify leads for B2B SaaS products?",
                "What strategies do you use to demonstrate ROI to potential SaaS customers?",
                "How do you handle long sales cycles typical in enterprise SaaS sales?",
                "Tell me about a time you lost a significant SaaS deal. What did you learn?"
            ]
            
            while self.question_count < self.max_questions and self.interview_active:
                print(f"📊 Question {self.question_count + 1} of {self.max_questions}")
                
                # Keep conversation history manageable
                if len(self.conversation_history) > 15:
                    self.conversation_history = self.conversation_history[-8:]

                # Generate or use fallback question
                question = None
                if hasattr(self.bot, 'query_gemini') and len(self.conversation_history) > 0:
                    try:
                        system_prompt = f"""As a friendly and professional SaaS sales interviewer, ask one engaging question based on this conversation context.
The question should:
- Be encouraging and conversational
- Build on what the candidate has shared about their sales background
- Test practical SaaS sales knowledge and experience
- Be appropriate for a sales professional
- Keep it to one clear question
- Focus on real-world SaaS sales scenarios
- Avoid repeating previous questions
- short and concise

Recent conversation: {' '.join([msg['content'] for msg in self.conversation_history[-4:]])}

Generate only the question in a friendly, professional tone."""

                        response = self.bot.query_gemini(system_prompt)
                        if response and response.strip():
                            question = response.strip()
                    except Exception as e:
                        print(f"Error generating question with Gemini: {e}")
                
                # Use fallback question if Gemini failed or no question generated
                if not question and self.question_count < len(fallback_questions):
                    question = fallback_questions[self.question_count]
                elif not question:
                    question = "What do you think is the most important skill for a successful SaaS salesperson?"

                print(f"❓ Asking question: {question}")
                self.current_question = question
                self.bot.speak(question)

                # Wait for and process answer
                print("⏳ Waiting for user answer...")
                answer = self.bot.listen()
                print(f"💬 Received answer: {answer}")

                if answer and "didn't receive a response" not in answer and len(answer.split()) > 2:
                    # Add both question and answer to history
                    self.conversation_history.append({"role": "assistant", "content": question})
                    self.conversation_history.append({"role": "user", "content": answer})

                    # Provide encouraging feedback
                    try:
                        feedback_prompt = f"""You are a friendly SaaS sales interviewer. The candidate just said:

                    "{answer}"

                    Respond with one thoughtful follow-up comment. It should:
                    - Be relevant to the content
                    - Encourage further elaboration or reflection
                    - Be very short (1–2 sentences)
                    - Avoid generic phrases like "That's great"

                    Say only the comment, nothing else.
                    """
                        feedback = self.bot.query_gemini(feedback_prompt)
                        if feedback:
                            self.bot.speak(feedback.strip())
                        else:
                            self.bot.speak("Thanks for sharing that.")
                    except Exception as e:
                        print(f"Gemini feedback error: {e}")
                        self.bot.speak("Thanks for sharing that.")

            
                    
                    self.question_count += 1
                    print(f"✅ Question {self.question_count} completed")
                else:
                    # If no proper response, try one more time
                    print("⚠️ No proper response received, asking follow-up...")
                    self.bot.speak("I'd love to hear more about your experience. Could you elaborate on that?")
                    retry_answer = self.bot.listen()
                    
                    if retry_answer and "didn't receive a response" not in retry_answer and len(retry_answer.split()) > 2:
                        self.conversation_history.append({"role": "assistant", "content": question})
                        self.conversation_history.append({"role": "user", "content": retry_answer})
                        self.bot.speak("Thank you for sharing that.")
                        self.question_count += 1
                    else:
                        # Move on to next question
                        self.bot.speak("Let me ask you a different question.")
                        self.question_count += 1

                # Small delay between questions
                if self.interview_active and self.question_count < self.max_questions:
                    time.sleep(1.0)

            # Conclude Interview
            if self.interview_active:
                print("🏁 Concluding interview...")
                self._conclude_interview()

        except Exception as e:
            print(f"❌ Interview logic error: {e}")
            print(traceback.format_exc())
            if self.interview_active:
                self.bot.speak("We've encountered a technical issue. Thank you for your time today!")
            self.interview_active = False

    def _conclude_interview(self):
        """Conclude the interview"""
        if not self.interview_active:
            return
            
        try:
            print("🎬 Starting interview conclusion...")
            socketio.emit('interview_phase', {'phase': 'conclusion'})
            
            self.bot.speak("That was a great conversation. Thank you for sharing your insights about SaaS sales.")
            time.sleep(0.5)

            self.bot.speak("Do you have any questions for me about the role, the company, or the next steps?")
            final_questions = self.bot.listen()

            if final_questions and "didn't receive a response" not in final_questions:
                self.conversation_history.append({"role": "user", "content": final_questions})
                self.bot.speak("Those are great questions! The hiring team will be in touch with more details on the next steps very soon.")
            else:
                self.bot.speak("If you don't have any questions right now, that's perfectly fine.")

            time.sleep(0.5)
            self.bot.speak("Thank you so much for your time today. It was a pleasure speaking with you, and I wish you the best of luck!")
            
            socketio.emit('interview_complete', {
                'message': 'Interview completed successfully!',
                'conversation_history': self.conversation_history
            })

        except Exception as e:
            print(f"Error in interview conclusion: {e}")
        finally:
            self.interview_active = False

    def process_user_response(self, message):
        """Process user's response"""
        print(f"📝 Processing user response: '{message}'")
        
        if not message or not message.strip():
            print("⚠️ Empty message received")
            return
            
        if self.waiting_for_response:
            self.user_response = message.strip()
            print(f"✅ Response set: '{self.user_response}'")
            self.response_event.set()  # Signal that response was received
            print("🚨 Event triggered!")
        else:
            print("⚠️ Not currently waiting for response")
    
    def analyze_video_frame(self, frame_data):
        """Analyze video frame for monitoring using original bot logic"""
        if not self.bot or not self.interview_active:
            return
        
        try:
            # Decode base64 frame
            frame_bytes = base64.b64decode(frame_data.split(',')[1])
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Use your existing face detection logic
            if hasattr(self.bot, 'face_cascade') and self.bot.face_cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.bot.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                # Check for violations using your original logic
                if len(faces) == 0:
                    socketio.emit('monitoring_alert', {
                        'type': 'no_face',
                        'message': 'Please ensure your face is visible to the camera',
                        'severity': 'warning'
                    })
                elif len(faces) > 1:
                    socketio.emit('monitoring_alert', {
                        'type': 'multiple_faces',
                        'message': 'Multiple faces detected. Please ensure you are alone.',
                        'severity': 'warning'
                    })
                
        except Exception as e:
            print(f"Video analysis error: {e}")
    
    def end_interview(self):
        """End the interview"""
        try:
            print("🛑 Ending interview...")
            self.interview_active = False
            self.waiting_for_response = False
            
            # Unblock any waiting threads
            if hasattr(self, 'response_event'):
                self.response_event.set()
                
            # Wait for interview thread to finish
            if self.interview_thread and self.interview_thread.is_alive():
                self.interview_thread.join(timeout=2.0)
                
            if self.bot and hasattr(self.bot, 'cleanup'):
                self.bot.cleanup()
                
            return True, "Interview ended successfully"
        except Exception as e:
            print(f"Error ending interview: {e}")
            return False, f"Error ending interview: {str(e)}"

# Global bot instance
web_bot = WebInterviewBot()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'hihi_available': HIHI_AVAILABLE,
        'interview_active': web_bot.interview_active,
        'waiting_for_response': web_bot.waiting_for_response,
        'message': 'Flask backend is running'
    })

@app.route('/api/reset', methods=['POST'])
def reset_state():
    """Reset interview state - useful for development"""
    try:
        success, message = web_bot.reset_state()
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to reset state: {str(e)}'
        }), 500

@app.route('/api/initialize', methods=['POST'])
def initialize():
    """Initialize the interview bot"""
    try:
        success, message = web_bot.initialize_bot()
        return jsonify({
            'success': success,
            'message': message,
            'error': None if success else message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Initialization failed: {str(e)}',
            'error': str(e)
        }), 500

@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    """This endpoint is deprecated — interview now starts via socket after client_ready."""
    
    # ❌ Disabled to avoid early Polly voice before frontend is connected
    # success, message = web_bot.start_interview()

    return jsonify({
        'success': False,
        'message': 'Interview now starts via socket after client_ready.',
        'error': 'Deprecated endpoint'
    }), 400


@app.route('/api/end-interview', methods=['POST'])
def end_interview():
    """End the interview"""
    try:
        success, message = web_bot.end_interview()
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to end interview: {str(e)}'
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current interview status"""
    return jsonify({
        'interview_active': web_bot.interview_active,
        'waiting_for_response': web_bot.waiting_for_response,
        'question_count': web_bot.question_count,
        'max_questions': web_bot.max_questions
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('👋 Client connected')
    emit('connection_status', {'status': 'connected'})

@socketio.on("client_ready")
def on_client_ready():
    print("✅ Frontend is ready. Starting interview.")
    web_bot.start_interview()


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('👋 Client disconnected')

@socketio.on('user_message')
def handle_user_message(data):
    """Handle user text message"""
    try:
        message = data.get('message', '').strip()
        print(f"📨 Received user message via socket: '{message}'")
        
        if not message:
            print("⚠️ Empty message received")
            emit('error', {'message': 'Empty message received'})
            return
            
        # Process the response
        web_bot.process_user_response(message)
        
        # Send confirmation back to frontend
        emit('message_received', {
            'message': 'Response received and processed',
            'timestamp': time.time()
        })
        
    except Exception as e:
        print(f"❌ Error handling user message: {e}")
        print(traceback.format_exc())
        emit('error', {'message': f'Failed to process your message: {str(e)}'})

@socketio.on('video_frame')
def handle_video_frame(data):
    """Handle video frame for monitoring"""
    try:
        web_bot.analyze_video_frame(data['frame'])
    except Exception as e:
        print(f"Error handling video frame: {e}")

@socketio.on('tab_change')
def handle_tab_change():
    """Handle tab change detection"""
    try:
        emit('monitoring_alert', {
            'type': 'tab_change',
            'message': 'Please stay focused on the interview',
            'severity': 'warning'
        })
    except Exception as e:
        print(f"Error handling tab change: {e}")

if __name__ == '__main__':
    print("🚀 Starting Flask backend...")
    print(f"HIHI module available: {HIHI_AVAILABLE}")
    if not HIHI_AVAILABLE:
        print("⚠️ Warning: hihi.py not found or SaaSInterviewBot class not available")
    
    # Reset state on startup
    web_bot.reset_state()
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
