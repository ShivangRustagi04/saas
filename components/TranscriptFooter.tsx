"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Send, Loader2, CheckCircle } from "lucide-react"

interface Message {
  speaker: "AI" | "User"
  message: string
  timestamp: number
}

interface TranscriptFooterProps {
  transcript: Message[]
  onSendMessage: (message: string) => void
  waitingForResponse?: boolean
  isAISpeaking?: boolean
  messageReceived?: boolean
}

export default function TranscriptFooter({
  transcript,
  onSendMessage,
  waitingForResponse = false,
  isAISpeaking = false,
  messageReceived = false,
}: TranscriptFooterProps) {
  const [inputMessage, setInputMessage] = useState("")
  const [isExpanded, setIsExpanded] = useState(true) // Start expanded to encourage responses
  const transcriptRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [transcript])

  useEffect(() => {
    // Auto-expand when waiting for response
    if (waitingForResponse) {
      setIsExpanded(true)
    }
  }, [waitingForResponse])

  const handleSendMessage = () => {
    if (inputMessage.trim() && !isAISpeaking) {
      onSendMessage(inputMessage.trim())
      setInputMessage("")
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !isAISpeaking) {
      handleSendMessage()
    }
  }

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const getInputPlaceholder = () => {
    if (isAISpeaking) return "AI is speaking... please wait"
    if (waitingForResponse) return "Type your response here and press Enter..."
    return "Type your message..."
  }

  const getStatusMessage = () => {
    if (messageReceived) return "✅ Response received!"
    if (isAISpeaking) return "🎤 AI is speaking..."
    if (waitingForResponse) return "⏳ Waiting for your response"
    return "💬 Ready for conversation"
  }

  const getStatusColor = () => {
    if (messageReceived) return "text-green-400"
    if (isAISpeaking) return "text-blue-400"
    if (waitingForResponse) return "text-yellow-400"
    return "text-gray-400"
  }

  return (
    <div className={`bg-gray-800 border-t border-gray-700 transition-all duration-300 ${isExpanded ? "h-64" : "h-20"}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-700 flex justify-between items-center">
        <div className="flex items-center space-x-4">
          <h3 className="text-white font-medium">Live Transcript</h3>
          <span className={`text-sm ${getStatusColor()}`}>{getStatusMessage()}</span>
        </div>
        <Button
          onClick={() => setIsExpanded(!isExpanded)}
          variant="ghost"
          size="sm"
          className="text-gray-400 hover:text-white"
        >
          {isExpanded ? "Minimize" : "Expand"}
        </Button>
      </div>

      {/* Transcript Area */}
      {isExpanded && (
        <div ref={transcriptRef} className="flex-1 p-4 overflow-y-auto max-h-40">
          {transcript.length === 0 ? (
            <div className="text-gray-500 text-center py-4">
              <p>Interview transcript will appear here...</p>
              <p className="text-sm mt-2">The AI will ask questions and wait for your responses.</p>
            </div>
          ) : (
            transcript.map((msg, index) => (
              <div key={index} className="mb-3">
                <div className="flex items-start space-x-2">
                  <span className={`text-xs font-medium ${msg.speaker === "AI" ? "text-blue-400" : "text-green-400"}`}>
                    {msg.speaker === "AI" ? "Gyani" : "You"}
                  </span>
                  <span className="text-xs text-gray-500">{formatTime(msg.timestamp)}</span>
                </div>
                <p className="text-white text-sm mt-1 ml-2 leading-relaxed">{msg.message}</p>
              </div>
            ))
          )}
        </div>
      )}

      {/* Message Input */}
      <div className="p-4 flex space-x-2">
        <Input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={getInputPlaceholder()}
          disabled={isAISpeaking}
          className={`flex-1 bg-gray-700 border-gray-600 text-white placeholder-gray-400 ${
            isAISpeaking ? "opacity-50 cursor-not-allowed" : ""
          } ${waitingForResponse ? "border-yellow-500 ring-1 ring-yellow-500" : ""}`}
        />
        <Button
          onClick={handleSendMessage}
          disabled={!inputMessage.trim() || isAISpeaking}
          className={`${
            waitingForResponse ? "bg-yellow-600 hover:bg-yellow-700" : "bg-blue-600 hover:bg-blue-700"
          } disabled:opacity-50`}
        >
          {messageReceived ? (
            <CheckCircle className="w-4 h-4" />
          ) : isAISpeaking ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>
    </div>
  )
}
