#!/usr/bin/env python3
"""Patch the pinned AnyDisplay Android client with the project's existing JSON pen telemetry channel."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
java = root / "android/app/src/main/java/dev/anydisplay/client/input"
router = java / "InputRouter.kt"
telemetry = java / "PenTelemetry.kt"

source = router.read_text(encoding="utf-8")
needle = "        for (body in encodePen(samples)) send(Proto.PEN, body)\n"
call = needle + "        // Preserve the project's independently working pressure telemetry in parallel with AnyDisplay input.\n        PenTelemetry.send(ev, index, rect)\n"
if "PenTelemetry.send(ev, index, rect)" not in source:
    if needle not in source:
        raise SystemExit("Could not locate InputRouter pen send point; upstream source changed.")
    router.write_text(source.replace(needle, call, 1), encoding="utf-8")

telemetry.write_text(r'''package dev.anydisplay.client.input

import android.view.MotionEvent
import android.graphics.RectF
import org.json.JSONObject
import java.net.InetSocketAddress
import java.net.Socket
import java.io.BufferedWriter
import java.io.OutputStreamWriter
import java.util.concurrent.LinkedBlockingDeque
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

/**
 * Parallel compatibility channel for the original USB Pen Display diagnostic protocol.
 * AnyDisplay's own binary PEN packets remain untouched and continue to drive native Windows input.
 */
internal object PenTelemetry {
    private const val PORT = 27183
    private val queue = LinkedBlockingDeque<String>(128)
    @Volatile private var started = false

    @Synchronized
    private fun startIfNeeded() {
        if (started) return
        started = true
        thread(name = "LegacyPenTelemetry", isDaemon = true) {
            while (true) {
                var socket: Socket? = null
                try {
                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.keepAlive = true
                    socket.connect(InetSocketAddress("127.0.0.1", PORT), 1500)
                    val writer = BufferedWriter(OutputStreamWriter(socket.getOutputStream(), Charsets.UTF_8))
                    writer.write(JSONObject().put("type", "hello").put("protocol", 2).toString())
                    writer.newLine()
                    writer.flush()
                    while (!socket.isClosed) {
                        val packet = queue.pollFirst(250, TimeUnit.MILLISECONDS) ?: continue
                        writer.write(packet)
                        writer.newLine()
                        writer.flush()
                    }
                } catch (_: Exception) {
                    try { Thread.sleep(800) } catch (_: InterruptedException) { }
                } finally {
                    try { socket?.close() } catch (_: Exception) { }
                }
            }
        }
    }

    fun send(event: MotionEvent, index: Int, videoRect: RectF) {
        startIfNeeded()
        if (event.pointerCount <= index || videoRect.width() <= 0f || videoRect.height() <= 0f) return
        val x = event.getX(index)
        val y = event.getY(index)
        val action = MotionEvent.actionToString(event.actionMasked)
        val tool = when (event.getToolType(index)) {
            MotionEvent.TOOL_TYPE_STYLUS -> "STYLUS"
            MotionEvent.TOOL_TYPE_ERASER -> "ERASER"
            MotionEvent.TOOL_TYPE_FINGER -> "FINGER"
            MotionEvent.TOOL_TYPE_MOUSE -> "MOUSE"
            else -> "UNKNOWN"
        }
        val hover = event.actionMasked == MotionEvent.ACTION_HOVER_ENTER ||
            event.actionMasked == MotionEvent.ACTION_HOVER_MOVE ||
            event.actionMasked == MotionEvent.ACTION_HOVER_EXIT
        val packet = JSONObject().apply {
            put("type", "pen")
            put("protocol", 2)
            put("tool", tool)
            put("action", action)
            put("pointerId", event.getPointerId(index))
            put("x", x.toDouble())
            put("y", y.toDouble())
            put("canvasX", (x - videoRect.left).toDouble())
            put("canvasY", (y - videoRect.top).toDouble())
            put("canvasWidth", videoRect.width().toDouble())
            put("canvasHeight", videoRect.height().toDouble())
            put("pressure", event.getPressure(index).coerceIn(0f, 1f).toDouble())
            put("tilt", event.getAxisValue(MotionEvent.AXIS_TILT, index).toDouble())
            put("orientation", event.getOrientation(index).toDouble())
            put("buttons", event.buttonState)
            put("hover", hover)
            put("contact", event.actionMasked == MotionEvent.ACTION_DOWN ||
                event.actionMasked == MotionEvent.ACTION_MOVE ||
                event.actionMasked == MotionEvent.ACTION_POINTER_DOWN)
            put("eventTime", event.eventTime)
        }.toString()
        if (!queue.offerLast(packet)) {
            queue.pollFirst()
            queue.offerLast(packet)
        }
    }
}
''', encoding="utf-8")
print("Patched AnyDisplay InputRouter and added PenTelemetry.kt")
