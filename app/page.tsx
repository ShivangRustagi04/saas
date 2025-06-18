"use client"

import { useState, useEffect } from "react"
import InterviewInterface from "@/components/InterviewInterface"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2 } from "lucide-react"

export default function Home() {
  const [interviewStarted, setInterviewStarted] = useState(false)
  const [botInitialized, setBotInitialized] = useState(false)
  const [isInitializing, setIsInitializing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendConnected, setBackendConnected] = useState(false)

  useEffect(() => {
    // Check backend connection first
    checkBackendConnection()
  }, [])

  const checkBackendConnection = async () => {
    try {
      const response = await fetch("http://localhost:5000/health", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      })

      if (response.ok) {
        setBackendConnected(true)
        setError(null)
      } else {
        throw new Error("Backend not responding")
      }
    } catch (error) {
      console.error("Backend connection failed:", error)
      setBackendConnected(false)
      setError("Cannot connect to backend server. Please make sure the Flask server is running on port 5000.")
    }
  }

  const initializeBot = async () => {
    if (!backendConnected) {
      setError("Backend server is not connected. Please check if Flask server is running.")
      return
    }

    setIsInitializing(true)
    setError(null)

    try {
      const response = await fetch("http://localhost:5000/api/initialize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      if (data.success) {
        setBotInitialized(true)
        setError(null)
      } else {
        throw new Error(data.error || "Failed to initialize bot")
      }
    } catch (error) {
      console.error("Failed to initialize bot:", error)
      setError(`Failed to initialize bot: ${error instanceof Error ? error.message : "Unknown error"}`)
    } finally {
      setIsInitializing(false)
    }
  }

  const startInterview = async () => {
  if (!botInitialized) {
    await initializeBot()
  }
  setInterviewStarted(true) // ⬅️ just switch screen to InterviewInterface
}


  if (!interviewStarted) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="text-center max-w-md w-full">
          <h1 className="text-4xl font-bold text-white mb-8">SaaS Sales Interview</h1>

          <p className="text-gray-300 mb-8">
            Welcome to your AI-powered sales interview. Make sure your camera and microphone are working properly.
          </p>

          {/* Connection Status */}
          <div className="mb-6">
            <div
              className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${
                backendConnected ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
              }`}
            >
              <div className={`w-2 h-2 rounded-full mr-2 ${backendConnected ? "bg-green-400" : "bg-red-400"}`}></div>
              {backendConnected ? "Backend Connected" : "Backend Disconnected"}
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <Alert className="mb-6 bg-red-900 border-red-700">
              <AlertDescription className="text-red-300">{error}</AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="space-y-4">
            {!backendConnected && (
              <Button
                onClick={checkBackendConnection}
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 text-lg w-full"
              >
                Retry Connection
              </Button>
            )}

            {backendConnected && !botInitialized && (
              <Button
                onClick={initializeBot}
                disabled={isInitializing}
                className="bg-yellow-600 hover:bg-yellow-700 text-white px-8 py-3 text-lg w-full"
              >
                {isInitializing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Initializing Bot...
                  </>
                ) : (
                  "Initialize Interview Bot"
                )}
              </Button>
            )}

            {botInitialized && (
              <Button
                onClick={startInterview}
                className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 text-lg w-full"
              >
                Start Interview
              </Button>
            )}
          </div>

          {/* Instructions */}
          <div className="mt-8 text-left">
            <h3 className="text-white font-semibold mb-2">Setup Instructions:</h3>
            <ol className="text-gray-400 text-sm space-y-1">
              <li>
                1. Make sure Flask backend is running:{" "}
                <code className="bg-gray-800 px-1 rounded">python flask_backend.py</code>
              </li>
              <li>2. Ensure your camera and microphone permissions are granted</li>
              <li>3. Check that port 5000 is not blocked by firewall</li>
              <li>4. Initialize the bot before starting the interview</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  return <InterviewInterface />
}
