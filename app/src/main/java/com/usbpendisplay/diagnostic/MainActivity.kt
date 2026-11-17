package com.usbpendisplay.diagnostic

import android.app.Activity
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import java.io.BufferedWriter
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private lateinit var panel: PenDiagnosticView
    private lateinit var link: PenLinkClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        link = PenLinkClient { connected ->
            runOnUiThread { if (::panel.isInitialized) panel.setPcLink(connected) }
        }
        PenLinkHolder.client = link
        panel = PenDiagnosticView(this)
        window.statusBarColor = Color.rgb(12, 17, 27)
        window.navigationBarColor = Color.rgb(12, 17, 27)
        setContentView(panel)
        link.start()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        panel.updateFrom(event)
        return true
    }

    override fun onGenericMotionEvent(event: MotionEvent): Boolean {
        panel.updateFrom(event)
        return true
    }

    override fun onDestroy() {
        if (::link.isInitialized) link.stop()
        PenLinkHolder.client = null
        super.onDestroy()
    }
}

/** Sends newline-delimited JSON over the ADB-reversed USB TCP tunnel. */
private class PenLinkClient(private val onConnection: (Boolean) -> Unit) {
    private val queue = LinkedBlockingQueue<String>(512)
    @Volatile private var running = false
    private var worker: Thread? = null

    fun start() {
        if (running) return
        running = true
        worker = thread(name = "PenUsbLink", isDaemon = true) {
            var reported = false
            while (running) {
                var socket: Socket? = null
                try {
                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.connect(InetSocketAddress("127.0.0.1", 27183), 1200)
                    val writer = BufferedWriter(OutputStreamWriter(socket.getOutputStream(), Charsets.UTF_8))
                    if (!reported) { reported = true; onConnection(true) }
                    writer.write("{\"type\":\"hello\",\"protocol\":1}")
                    writer.newLine()
                    writer.flush()
                    while (running && !socket.isClosed) {
                        val message = queue.poll(300, java.util.concurrent.TimeUnit.MILLISECONDS)
                        if (message != null) {
                            writer.write(message)
                            writer.newLine()
                            writer.flush()
                        }
                    }
                } catch (_: Exception) {
                    if (reported) { reported = false; onConnection(false) }
                    try { Thread.sleep(900) } catch (_: InterruptedException) { }
                } finally {
                    try { socket?.close() } catch (_: Exception) { }
                }
            }
            if (reported) onConnection(false)
        }
    }

    fun send(message: String) {
        if (!running) return
        if (!queue.offer(message)) {
            queue.poll()
            queue.offer(message)
        }
    }

    fun stop() {
        running = false
        worker?.interrupt()
        worker = null
        queue.clear()
    }
}

private class PenDiagnosticView(context: android.content.Context) : View(context) {
    init { isFocusable = true; isFocusableInTouchMode = true }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        updateFrom(event)
        return true
    }

    override fun onGenericMotionEvent(event: MotionEvent): Boolean {
        updateFrom(event)
        return true
    }
    private val heading = Paint(3).apply { color = Color.WHITE; textSize = 27f; typeface = Typeface.DEFAULT_BOLD }
    private val body = Paint(3).apply { color = Color.rgb(210, 220, 235); textSize = 17f }
    private val muted = Paint(3).apply { color = Color.rgb(145, 160, 180); textSize = 13f }
    private val line = Paint(3).apply { color = Color.rgb(55, 70, 90); strokeWidth = 1.5f }
    private val dot = Paint(3).apply { color = Color.rgb(70, 190, 255) }
    private var tool = "Waiting for stylus..."
    private var device = "—"
    private var eventName = "No input yet"
    private var x = 0f
    private var y = 0f
    private var pressure = 0f
    private var tilt = 0f
    private var orientation = 0f
    private var buttons = 0
    private var hover = false
    private var contact = false
    private var received = false
    private var pcLink = false

    fun setPcLink(connected: Boolean) {
        pcLink = connected
        invalidate()
    }

    fun updateFrom(e: MotionEvent) {
        val i = e.actionIndex.coerceIn(0, e.pointerCount - 1)
        tool = when (e.getToolType(i)) {
            MotionEvent.TOOL_TYPE_STYLUS -> "STYLUS"
            MotionEvent.TOOL_TYPE_ERASER -> "ERASER"
            MotionEvent.TOOL_TYPE_FINGER -> "FINGER"
            MotionEvent.TOOL_TYPE_MOUSE -> "MOUSE"
            else -> "UNKNOWN"
        }
        device = e.device?.name ?: "Device #${e.deviceId}"
        eventName = MotionEvent.actionToString(e.action)
        x = e.getX(i); y = e.getY(i); pressure = e.getPressure(i)
        tilt = e.getAxisValue(MotionEvent.AXIS_TILT, i)
        orientation = e.getOrientation(i); buttons = e.buttonState
        hover = e.actionMasked in listOf(MotionEvent.ACTION_HOVER_ENTER, MotionEvent.ACTION_HOVER_MOVE, MotionEvent.ACTION_HOVER_EXIT)
        contact = e.actionMasked in listOf(MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE, MotionEvent.ACTION_POINTER_DOWN, MotionEvent.ACTION_POINTER_UP)
        received = true
        val payload = org.json.JSONObject().apply {
            put("type", "pen"); put("tool", tool); put("device", device); put("action", eventName)
            put("x", x.toDouble()); put("y", y.toDouble()); put("pressure", pressure.toDouble())
            put("tilt", tilt.toDouble()); put("orientation", orientation.toDouble())
            put("buttons", buttons); put("hover", hover); put("contact", contact); put("eventTime", e.eventTime)
        }
        PenLinkHolder.client?.send(payload.toString())
        invalidate()
    }

    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        val p = 28f
        var yText = 55f
        c.drawText("USB PEN DISPLAY", p, yText, heading); yText += 32f
        c.drawText("Build 0.2.0  •  USB stylus link test", p, yText, muted); yText += 28f
        c.drawLine(p, yText, width - p, yText, line); yText += 36f
        val state = if (!received) "WAITING" else if (contact) "CONTACT" else if (hover) "HOVER" else "INPUT"
        c.drawText("INPUT STATUS: $state", p, yText, heading); yText += 34f
        c.drawText("PC USB LINK: ${if (pcLink) "CONNECTED" else "WAITING FOR PC"}", p, yText, if (pcLink) body else muted); yText += 34f
        val rows = listOf(
            "Tool type" to tool, "Input device" to device, "Event" to eventName,
            "X position" to if (received) "%.1f px".format(x) else "—",
            "Y position" to if (received) "%.1f px".format(y) else "—",
            "Pressure" to "%.4f (Android raw value)".format(pressure),
            "Tilt" to "%.4f rad / %.1f°".format(tilt, Math.toDegrees(tilt.toDouble())),
            "Orientation" to "%.4f rad".format(orientation), "Button state" to buttons.toString()
        )
        for ((label, value) in rows) {
            c.drawText(label, p, yText, muted)
            c.drawText(value, p + 145f, yText, body)
            yText += 29f
        }
        val top = yText + 8f
        val bottom = height - 55f
        if (bottom > top + 80f) {
            c.drawLine(p, top, width - p, top, line)
            c.drawText("DRAWING AREA — move the pen here", p, top + 27f, muted)
            c.drawRect(p, top + 42f, width - p, bottom, line)
            if (received) c.drawCircle(x.coerceIn(p, width - p), y.coerceIn(top + 42f, bottom), 7f + pressure.coerceIn(0f, 1f) * 12f, dot)
        }
        c.drawText("Pen events are sent to Windows when the USB link is active.", p, height - 22f, muted)
    }
}

/** A small holder lets the custom View enqueue events without blocking the UI thread. */
private object PenLinkHolder { var client: PenLinkClient? = null }
