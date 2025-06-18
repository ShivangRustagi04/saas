import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Mic, MicOff, Video, VideoOff, Phone, MessageCircle, Volume2, VolumeX, CheckCircle, Headphones } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface Message {
  speaker: "AI" | "User"
  message: string
  timestamp: number
}

const VideoFeed = ({ isVideoOff, isMuted, onVideoFrame }) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    if (!isVideoOff) {
      navigator.mediaDevices.getUserMedia({ video: true, audio: !isMuted })
        .then(stream => {
          streamRef.current = stream
          if (videoRef.current) {
            videoRef.current.srcObject = stream
          }
        })
        .catch(err => console.error('Error accessing camera:', err))
    } else {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
      }
    }
  }, [isVideoOff, isMuted])

  if (isVideoOff) {
    return (
      <div className="w-full h-full bg-gray-700 flex items-center justify-center">
        <div className="text-white text-center">
          <VideoOff className="w-16 h-16 mx-auto mb-4" />
          <p>Camera is off</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-full relative">
      <video
        ref={videoRef}
        autoPlay
        muted
        className="w-full h-full object-cover"
      />
      <canvas ref={canvasRef} className="hidden" />
    </div>
  )
}

const AIAvatar = ({ isAISpeaking }) => (
  <div className="w-full h-full bg-gray-700 flex flex-col items-center justify-center p-4">
    <div className={`w-32 h-32 rounded-full ${isAISpeaking ? 'bg-blue-500 animate-pulse' : 'bg-gray-500'} mb-4 flex items-center justify-center`}>
      <div className="text-white text-2xl">AI</div>
    </div>
    <div className="text-white text-center text-lg">
      Gyani AI Interviewer
    </div>
  </div>
)

const TranscriptFooter = ({ transcript, onSendMessage, waitingForResponse, isAISpeaking, messageReceived }) => {
  const [inputMessage, setInputMessage] = useState("")

  return (
    <div className="bg-gray-800 p-4 border-t border-gray-700">
      <div className="max-h-32 overflow-y-auto mb-4">
        {transcript.slice(-3).map((msg, idx) => (
          <div key={idx} className={`text-sm mb-1 ${msg.speaker === 'AI' ? 'text-blue-300' : 'text-green-300'}`}>
            <strong>{msg.speaker}:</strong> {msg.message}
          </div>
        ))}
      </div>
      <div className="flex space-x-2">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          placeholder="Type your response..."
          className="flex-1 bg-gray-700 text-white p-2 rounded"
          disabled={isAISpeaking}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && inputMessage.trim()) {
              onSendMessage(inputMessage.trim())
              setInputMessage("")
            }
          }}
        />
        <Button 
          onClick={() => {
            if (inputMessage.trim()) {
              onSendMessage(inputMessage.trim())
              setInputMessage("")
            }
          }}
          disabled={isAISpeaking || !inputMessage.trim()}
        >
          Send
        </Button>
      </div>
    </div>
  )
}

export default function InterviewInterface() {
  const [isMuted, setIsMuted] = useState(false)
  const [isVideoOff, setIsVideoOff] = useState(false)
  const [isAudioMuted, setIsAudioMuted] = useState(false)
  const [transcriptHistory, setTranscriptHistory] = useState<Message[]>([])
  const [currentAIMessage, setCurrentAIMessage] = useState("")
  const [isAISpeaking, setIsAISpeaking] = useState(false)
  const [interviewPhase, setInterviewPhase] = useState("introduction")
  const [waitingForResponse, setWaitingForResponse] = useState(false)
  const [responseTimeout, setResponseTimeout] = useState(60)
  const [alerts, setAlerts] = useState<Array<{ id: number; message: string; type: string }>>([])
  const [messageReceived, setMessageReceived] = useState(false)
  const [voiceInputEnabled, setVoiceInputEnabled] = useState(true)
  const [isListening, setIsListening] = useState(false)
  const [speechRecognitionSupported, setSpeechRecognitionSupported] = useState(false)
  const [socketConnected, setSocketConnected] = useState(false)
  const [connectionAttempts, setConnectionAttempts] = useState(0)

  const alertIdRef = useRef(0)
  const speechSynthRef = useRef<SpeechSynthesis | null>(null)
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const autoStartTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const recognitionRef = useRef<any>(null)
  const silenceTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const socketRef = useRef<any>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const audioQueueRef = useRef<HTMLAudioElement[]>([])
  const isAudioPlayingRef = useRef(false)

  const processPollyQueue = () => {
    if (isAudioPlayingRef.current || audioQueueRef.current.length === 0) return;

    const nextAudio = audioQueueRef.current.shift();
    if (!nextAudio) return;

    isAudioPlayingRef.current = true;

    nextAudio.onplay = () => {
      setIsAISpeaking(true);
      console.log("✅ Polly audio started");
    };

    nextAudio.onended = () => {
      setIsAISpeaking(false);
      isAudioPlayingRef.current = false;
      console.log("✅ Polly audio ended");
      processPollyQueue(); // 🔁 Continue to next
    };

    nextAudio.onerror = (e) => {
      console.error("❌ Polly audio error:", e);
      setIsAISpeaking(false);
      isAudioPlayingRef.current = false;
      processPollyQueue();
    };

    nextAudio.play().catch((err) => {
      console.error("❌ Polly audio failed to play:", err);
      setIsAISpeaking(false);
      isAudioPlayingRef.current = false;
      processPollyQueue();
    });
  };
  // SocketIO connection using socket.io-client
  const connectSocket = () => {
    try {
      // Import socket.io-client dynamically for client-side
      const io = require('socket.io-client')
      
      // Connect to Flask-SocketIO server
      const serverUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000'
      console.log(`Attempting to connect to: ${serverUrl}`)
      
      const socket = io(serverUrl, {
        transports: ['websocket', 'polling'],
        timeout: 20000,
        forceNew: true
      })
      
      socket.on('connect', () => {
        console.log('SocketIO connected successfully')
        setSocketConnected(true)
        setConnectionAttempts(0)
        addAlert("Connected to interview server", "success")
        
        // Start with initial AI message after connection
        socket.emit("client_ready");
      });


      socket.on("ai_response", (data: any) => {
        console.log("📡 Received ai_response:", data);
        console.log("🔊 Polly audio present?", !!data.audio);
        console.log("🎧 Audio base64 preview:", data.audio?.slice(0, 30));
        if (data.audio) {
          const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
          audioQueueRef.current.push(audio); // 📦 Queue the audio
          processPollyQueue();               // ▶️ Start processing queue
        } else {
          console.warn("⚠️ Polly audio missing, using fallback voice.");
          const utterance = new SpeechSynthesisUtterance(data.message);
          utterance.onstart = () => setIsAISpeaking(true);
          utterance.onend = () => setIsAISpeaking(false);
          speechSynthRef.current?.speak(utterance);
        }


  // Append message to transcript
        const message: Message = {
          speaker: "AI",
          message: data.message,
          timestamp: Date.now(),
        };

        setTranscriptHistory(prev => [...prev, message]);
        setCurrentAIMessage(data.message);
        setIsAISpeaking(true);
        setWaitingForResponse(false);
      });


      socket.on('connection_response', (data) => {
        console.log('Connection response:', data)
        console.log("📢 AI responded:", data);
        console.log("✅ Polly audio received?", !!data.audio);
        console.log("🎧 Audio preview:", data.audio?.slice(0, 50));  // Show start of base64 string

        addAlert(data.message || "Connected successfully", "success")
      })

      socket.on('error', (error) => {
        console.error('SocketIO error:', error)
        addAlert("Connection error occurred", "error")
      })
      
      socket.on('disconnect', (reason) => {
        console.log('SocketIO disconnected:', reason)
        setSocketConnected(false)
        addAlert("Disconnected from server", "error")
        
        // Attempt to reconnect
        if (reason === 'io server disconnect') {
          // Server initiated disconnect, don't reconnect
          addAlert("Server ended the connection", "info")
        } else {
          // Client disconnect, attempt to reconnect
          attemptReconnect()
        }
      })
      
      socket.on('connect_error', (error) => {
        console.error('Connection error:', error)
        setSocketConnected(false)
        addAlert(`Connection failed: ${error.message || 'Unknown error'}`, "error")
        attemptReconnect()
      })
      
      socket.on('interview_ended', (data) => {
        console.log('Interview ended:', data)
        addAlert(data.message || "Interview ended", "info")
      })
      
      socketRef.current = socket
      
    } catch (error) {
      console.error('Failed to create socket connection:', error)
      addAlert("Failed to load socket.io library. Please ensure it's installed.", "error")
    }
  }

  const attemptReconnect = () => {
    if (connectionAttempts < 5) {
      const delay = Math.min(1000 * Math.pow(2, connectionAttempts), 10000) // Exponential backoff
      setConnectionAttempts(prev => prev + 1)
      
      addAlert(`Attempting to reconnect in ${delay/1000} seconds... (${connectionAttempts + 1}/5)`, "info")
      
      reconnectTimeoutRef.current = setTimeout(() => {
        if (!socketConnected) {
          connectSocket()
        }
      }, delay)
    } else {
      addAlert("Failed to reconnect after 5 attempts. Please refresh the page.", "error")
    }
  }

  const sendMessage = (message: string, eventName: string = 'user_message') => {
    if (socketRef.current && socketRef.current.connected) {
      const data = {
        message: message,
        timestamp: Date.now(),
        phase: interviewPhase
      }
      console.log(`Emitting ${eventName}:`, data)
      socketRef.current.emit(eventName, data)
      return true
    } else {
      addAlert("Not connected to server. Please wait for reconnection.", "error")
      return false
    }
  }

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SpeechRecognition) {
      setSpeechRecognitionSupported(true)
      
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = 'en-US'
      
      recognition.onstart = () => {
        setIsListening(true)
        console.log("Speech recognition started")
      }
      
      recognition.onresult = (event: any) => {
        let finalTranscript = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript
          }
        }
        
        if (finalTranscript.trim()) {
          console.log("Speech recognized:", finalTranscript.trim())
          sendUserMessage(finalTranscript.trim())
          stopListening()
        }
      }
      
      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
        addAlert(`Voice recognition error: ${event.error}`, "error")
        
        if (event.error === 'network') {
          setTimeout(() => {
            if (waitingForResponse && voiceInputEnabled && !isMuted) {
              startListening()
            }
          }, 2000)
        }
      }
      
      recognition.onend = () => {
        setIsListening(false)
        console.log("Speech recognition ended")
        
        if (waitingForResponse && voiceInputEnabled && !isMuted) {
          setTimeout(() => {
            startListening()
          }, 1000)
        }
      }
      
      recognitionRef.current = recognition
    } else {
      addAlert("Voice recognition not supported in this browser. Please use Chrome or Edge.", "warning")
    }

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      speechSynthRef.current = window.speechSynthesis
    }

    // Connect to SocketIO server
    connectSocket()

    return () => {
      if (speechSynthRef.current) {
        speechSynthRef.current.cancel()
      }
      stopListening()
      if (autoStartTimeoutRef.current) {
        clearTimeout(autoStartTimeoutRef.current)
      }
      if (silenceTimeoutRef.current) {
        clearTimeout(silenceTimeoutRef.current)
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, [])

  useEffect(() => {
    if (waitingForResponse && voiceInputEnabled && !isMuted && !isAISpeaking && speechRecognitionSupported && !isListening) {
      autoStartTimeoutRef.current = setTimeout(() => {
        if (waitingForResponse && voiceInputEnabled && !isMuted && !isListening) {
          startListening()
        }
      }, 2000)
    }

    return () => {
      if (autoStartTimeoutRef.current) {
        clearTimeout(autoStartTimeoutRef.current)
      }
    }
  }, [waitingForResponse, voiceInputEnabled, isMuted, isAISpeaking, isListening])

  useEffect(() => {
    if (!isAISpeaking && currentAIMessage && !waitingForResponse) {
      setTimeout(() => {
        setWaitingForResponse(true)
      }, 1000)
    }
  }, [isAISpeaking, currentAIMessage, waitingForResponse])

  const startListening = () => {
    if (!isMuted && voiceInputEnabled && speechRecognitionSupported && recognitionRef.current && !isListening) {
      try {
        recognitionRef.current.start()
        addAlert("Listening for your response...", "info")
      } catch (error) {
        console.error('Error starting speech recognition:', error)
        addAlert("Failed to start voice recognition", "error")
      }
    }
  }

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      try {
        recognitionRef.current.stop()
      } catch (error) {
        console.error('Error stopping speech recognition:', error)
      }
    }
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current)
    }
    setIsListening(false)
  }

  const toggleVoiceInput = () => {
    const newState = !voiceInputEnabled
    setVoiceInputEnabled(newState)
    if (!newState) stopListening()
    addAlert(`Voice input ${newState ? "enabled" : "disabled"}`, newState ? "success" : "info")
  }

  const speakMessage = (text: string) => {
    if (!speechSynthRef.current || isAudioMuted) {
      setIsAISpeaking(false)
      return
    }

    speechSynthRef.current.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.9
    utterance.pitch = 1.0
    utterance.volume = 1.0

    utterance.onstart = () => {
      setIsAISpeaking(true)
      console.log("AI started speaking")
    }
    
    utterance.onend = () => {
      setIsAISpeaking(false)
      console.log("AI finished speaking")
    }
    
    utterance.onerror = () => {
      setIsAISpeaking(false)
      console.log("AI speech error")
    }

    currentUtteranceRef.current = utterance
  }

  const sendUserMessage = (message: string) => {
    if (!message.trim()) return

    console.log("Sending user message:", message.trim())
    
    const userMessage: Message = {
      speaker: "User",
      message: message.trim(),
      timestamp: Date.now(),
    }
    
    setTranscriptHistory(prev => [...prev, userMessage])
    setWaitingForResponse(false)
    setMessageReceived(true)
    
    if (sendMessage(message.trim(), 'user_message')) {
      addAlert("Message sent to AI", "success")
      setTimeout(() => setMessageReceived(false), 2000)
    }
  }

  const addAlert = (message: string, type: string) => {
    const id = alertIdRef.current++
    setAlerts(prev => [...prev, { id, message, type }])
    setTimeout(() => setAlerts(prev => prev.filter(alert => alert.id !== id)), 5000)
  }

  const toggleMute = () => {
    setIsMuted(!isMuted)
    if (!isMuted) stopListening()
    addAlert(`Microphone ${!isMuted ? "muted" : "unmuted"}`, !isMuted ? "info" : "success")
  }

  const toggleVideo = () => {
    setIsVideoOff(!isVideoOff)
    addAlert(`Camera ${!isVideoOff ? "turned off" : "turned on"}`, !isVideoOff ? "info" : "success")
  }

  const toggleAudio = () => {
    setIsAudioMuted(!isAudioMuted)
    if (!isAudioMuted && speechSynthRef.current) {
      speechSynthRef.current.cancel()
      setIsAISpeaking(false)
    }
    addAlert(`AI Audio ${!isAudioMuted ? "muted" : "unmuted"}`, !isAudioMuted ? "info" : "success")
  }

  const endCall = () => {
    stopListening()
    if (speechSynthRef.current) {
      speechSynthRef.current.cancel()
    }
    if (socketRef.current && socketRef.current.connected) {
      sendMessage("Interview ended by user", "end_interview")
      socketRef.current.disconnect()
    }
    addAlert("Interview ended successfully", "success")
    setSocketConnected(false)
    setTimeout(() => {
      addAlert("You can now close this window", "info")
    }, 2000)
  }

  const testConnection = () => {
    if (socketRef.current && socketRef.current.connected) {
      socketRef.current.emit('ping')
      addAlert("Connection test sent", "info")
    } else {
      addAlert("Not connected - attempting to reconnect", "warning")
      connectSocket()
    }
  }

  const getPhaseDisplay = () => {
    switch (interviewPhase) {
      case "introduction": return "Introduction Phase"
      case "sales_questions": return "Sales Questions Phase"
      case "conclusion": return "Conclusion Phase"
      default: return "Interview in Progress"
    }
  }

  const getResponseStatus = () => {
    if (messageReceived) return "Response received ✓"
    if (isListening) return "🎤 Listening..."
    if (waitingForResponse) return `Waiting for your response`
    if (isAISpeaking) return "AI is speaking..."
    return socketConnected ? "Ready" : "Connecting..."
  }

  const getResponseStatusColor = () => {
    if (messageReceived) return "text-green-400"
    if (isListening) return "text-red-400"
    if (waitingForResponse) return "text-yellow-400"
    if (isAISpeaking) return "text-blue-400"
    return socketConnected ? "text-gray-400" : "text-orange-400"
  }

  return (
    <div className="h-screen bg-gray-900 flex flex-col">
      <div className="bg-gray-800 p-4 flex justify-between items-center">
        <div>
          <h1 className="text-white text-xl font-semibold">SaaS Sales Interview</h1>
          <p className="text-gray-400 text-sm">{getPhaseDisplay()}</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            {messageReceived && <CheckCircle className="w-4 h-4 text-green-400" />}
            {isListening && <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse"></div>}
            <span className={`text-sm ${getResponseStatusColor()}`}>{getResponseStatus()}</span>
          </div>

          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${
              socketConnected ? "bg-green-400" : "bg-red-400"
            }`}></div>
            <span className="text-white text-sm">
              {socketConnected ? "Connected" : `Disconnected ${connectionAttempts > 0 ? `(${connectionAttempts}/5)` : ''}`}
            </span>
          </div>

          {!socketConnected && (
            <Button onClick={testConnection} variant="outline" size="sm">
              Test Connection
            </Button>
          )}

          {speechRecognitionSupported && (
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${voiceInputEnabled && !isMuted ? "bg-green-400" : "bg-red-400"}`}></div>
              <span className="text-white text-sm">
                {voiceInputEnabled && !isMuted ? "Voice On" : "Voice Off"}
              </span>
            </div>
          )}

          <Button onClick={endCall} variant="destructive" className="bg-red-600 hover:bg-red-700">
            End Interview
          </Button>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="absolute top-20 right-4 z-50 space-y-2">
          {alerts.map((alert) => (
            <Alert
              key={alert.id}
              className={`w-80 ${
                alert.type === "success" ? "bg-green-900 border-green-700" :
                alert.type === "warning" ? "bg-yellow-900 border-yellow-700" :
                alert.type === "info" ? "bg-blue-900 border-blue-700" :
                "bg-red-900 border-red-700"
              }`}
            >
              <AlertDescription className="text-white">{alert.message}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      <div className="flex-1 flex">
        <div className="w-1/2 p-4">
          <div className="bg-gray-800 rounded-lg h-full relative overflow-hidden">
            <VideoFeed
              isVideoOff={isVideoOff}
              isMuted={isMuted}
              onVideoFrame={(frame) => console.log('Video frame captured')}
            />
            <div className="absolute bottom-4 left-4 bg-black bg-opacity-50 text-white px-2 py-1 rounded">You</div>

            {isListening && (
              <div className="absolute top-4 left-4 bg-red-600 text-white px-3 py-1 rounded-full text-sm flex items-center animate-pulse">
                <Mic className="w-4 h-4 mr-1" />
                Listening...
              </div>
            )}

            {waitingForResponse && !isListening && (
              <div className="absolute top-4 left-4 bg-yellow-600 text-white px-3 py-1 rounded-full text-sm flex items-center animate-pulse">
                <MessageCircle className="w-4 h-4 mr-1" />
                Your turn to respond
              </div>
            )}

            {messageReceived && (
              <div className="absolute top-4 left-4 bg-green-600 text-white px-3 py-1 rounded-full text-sm flex items-center">
                <CheckCircle className="w-4 h-4 mr-1" />
                Response received!
              </div>
            )}
          </div>
        </div>

        <div className="w-1/2 p-4">
          <div className="bg-gray-800 rounded-lg h-full relative overflow-hidden">
            <AIAvatar
              isAISpeaking={isAISpeaking}
            />
            <div className="absolute bottom-4 left-4 bg-black bg-opacity-50 text-white px-2 py-1 rounded">
              Gyani (AI Interviewer)
            </div>

            {isAISpeaking && (
              <div className="absolute top-4 left-4 bg-blue-600 text-white px-3 py-1 rounded-full text-sm flex items-center">
                <Volume2 className="w-4 h-4 mr-1" />
                Speaking...
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="bg-gray-800 p-4 flex justify-center space-x-4">
        <Button
          onClick={toggleMute}
          variant={isMuted ? "destructive" : "secondary"}
          size="lg"
          className="rounded-full w-12 h-12"
          title="Toggle Microphone"
        >
          {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
        </Button>

        <Button
          onClick={toggleVideo}
          variant={isVideoOff ? "destructive" : "secondary"}
          size="lg"
          className="rounded-full w-12 h-12"
          title="Toggle Camera"
        >
          {isVideoOff ? <VideoOff className="w-6 h-6" /> : <Video className="w-6 h-6" />}
        </Button>

        <Button
          onClick={toggleAudio}
          variant={isAudioMuted ? "destructive" : "secondary"}
          size="lg"
          className="rounded-full w-12 h-12"
          title="Toggle AI Audio"
        >
          {isAudioMuted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
        </Button>

        {speechRecognitionSupported && (
          <Button
            onClick={toggleVoiceInput}
            variant={voiceInputEnabled ? "secondary" : "destructive"}
            size="lg"
            className="rounded-full w-12 h-12"
            title="Toggle Voice Input"
          >
            <Headphones className="w-6 h-6" />
          </Button>
        )}

        {speechRecognitionSupported && (
          <Button
            onClick={isListening ? stopListening : startListening}
            variant={isListening ? "destructive" : "default"}
            size="lg"
            className="px-4"
            title={isListening ? "Stop Listening" : "Start Voice Response"}
          >
            {isListening ? <MicOff className="w-4 h-4 mr-2" /> : <Mic className="w-4 h-4 mr-2" />}
            {isListening ? "Stop" : "Speak"}
          </Button>
        )}

        <Button
          onClick={endCall}
          variant="destructive"
          size="lg"
          className="rounded-full w-12 h-12"
          title="End Interview"
        >
          <Phone className="w-6 h-6" />
        </Button>
      </div>

      <TranscriptFooter
        transcript={transcriptHistory}
        onSendMessage={sendUserMessage}
        waitingForResponse={waitingForResponse}
        isAISpeaking={isAISpeaking}
        messageReceived={messageReceived}
      />
    </div>
  )
}