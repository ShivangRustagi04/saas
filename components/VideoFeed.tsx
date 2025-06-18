"use client"

import { useEffect, useRef } from "react"

interface VideoFeedProps {
  isVideoOff: boolean
  isMuted: boolean
  onVideoFrame?: (frame: string) => void
}

export default function VideoFeed({ isVideoOff, isMuted, onVideoFrame }: VideoFeedProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    startCamera()
    return () => {
      stopCamera()
    }
  }, [])

  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !isMuted
      })
    }
  }, [isMuted])

  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.getVideoTracks().forEach((track) => {
        track.enabled = !isVideoOff
      })
    }
  }, [isVideoOff])

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      })

      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }

      // Start sending frames for monitoring
      startFrameCapture()
    } catch (error) {
      console.error("Error accessing camera:", error)
    }
  }

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
    }
  }

  const startFrameCapture = () => {
    const captureFrame = () => {
      if (videoRef.current && canvasRef.current && onVideoFrame) {
        const canvas = canvasRef.current
        const video = videoRef.current
        const ctx = canvas.getContext("2d")

        if (ctx) {
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
          ctx.drawImage(video, 0, 0)

          const frameData = canvas.toDataURL("image/jpeg", 0.8)
          onVideoFrame(frameData)
        }
      }

      setTimeout(captureFrame, 1000) // Capture every second
    }

    setTimeout(captureFrame, 1000)
  }

  return (
    <div className="w-full h-full relative">
      {!isVideoOff ? (
        <video ref={videoRef} autoPlay muted className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full bg-gray-700 flex items-center justify-center">
          <div className="text-white text-center">
            <div className="w-16 h-16 bg-gray-600 rounded-full mx-auto mb-4 flex items-center justify-center">
              <span className="text-2xl">👤</span>
            </div>
            <p>Camera is off</p>
          </div>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />

      {isMuted && <div className="absolute top-4 right-4 bg-red-600 text-white px-2 py-1 rounded text-sm">Muted</div>}
    </div>
  )
}
