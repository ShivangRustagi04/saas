"use client"

import { useEffect, useState } from "react"

interface AIAvatarProps {
  isAISpeaking: boolean
  currentMessage: string
  waitingForResponse?: boolean
}

export default function AIAvatar({ isAISpeaking, currentMessage, waitingForResponse }: AIAvatarProps) {
  const [animationClass, setAnimationClass] = useState("")

  useEffect(() => {
    if (isAISpeaking) {
      setAnimationClass("animate-pulse")
    } else if (waitingForResponse) {
      setAnimationClass("animate-bounce")
    } else {
      setAnimationClass("")
    }
  }, [isAISpeaking, waitingForResponse])

  const getStatusText = () => {
    if (isAISpeaking) return "Speaking..."
    if (waitingForResponse) return "Waiting for your response..."
    return "Listening..."
  }

  const getStatusColor = () => {
    if (isAISpeaking) return "text-blue-400"
    if (waitingForResponse) return "text-yellow-400"
    return "text-green-400"
  }

  return (
    <div className="w-full h-full bg-gradient-to-br from-blue-900 to-purple-900 flex items-center justify-center relative">
      {/* AI Avatar Circle */}
      <div
        className={`w-32 h-32 rounded-full bg-gradient-to-r from-blue-400 to-purple-500 flex items-center justify-center ${animationClass}`}
      >
        <div className="w-24 h-24 rounded-full bg-white bg-opacity-20 flex items-center justify-center">
          <div className="text-4xl">🤖</div>
        </div>
      </div>

      {/* Speaking/Status Indicator */}
      <div className="absolute bottom-20 left-1/2 transform -translate-x-1/2">
        {isAISpeaking && (
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
          </div>
        )}

        {waitingForResponse && (
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" style={{ animationDelay: "0.2s" }}></div>
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" style={{ animationDelay: "0.4s" }}></div>
          </div>
        )}
      </div>

      {/* Current Message Display */}
      {currentMessage && (
        <div className="absolute bottom-8 left-4 right-4 bg-black bg-opacity-50 text-white p-3 rounded-lg">
          <p className="text-sm">{currentMessage}</p>
        </div>
      )}

      {/* AI Status Indicator */}
      <div className="absolute top-4 right-4">
        <div className="flex items-center space-x-2">
          <div
            className={`w-2 h-2 rounded-full ${waitingForResponse ? "bg-yellow-400" : "bg-green-400"} ${isAISpeaking ? "animate-pulse" : ""}`}
          ></div>
          <span className={`text-xs ${getStatusColor()}`}>{getStatusText()}</span>
        </div>
      </div>
    </div>
  )
}
