package com.usbpendisplay.diagnostic

import android.app.Activity
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private lateinit var panel: PenCanvasView
    private lateinit var link: PenLinkClient
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(12, 17, 27)
        window.navigationBarColor = Color.rgb(12, 17, 27)
        link = PenLinkClient { connected -> runOnUiThread { if (::panel.isInitialized) panel.setPcLink(connected) } }
        PenLinkHolder.client = link
        panel = PenCanvasView(this)
        setContentView(panel)
        link.start()
    }
    override fun onDestroy() {
        if (::link.isInitialized) link.stop()
        PenLinkHolder.client = null
        super.onDestroy()
    }
}

private class PenLinkClient(private val onConnection: (Boolean) -> Unit) {
    private val queue = LinkedBlockingQueue<String>(2048)
    @Volatile private var running = false
    private var worker: Thread? = null
    fun start() {
        if (running) return
        running = true
        worker = thread(name = "PenUsbLink", isDaemon = true) {
            while (running) {
                var socket: Socket? = null
                try {
                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.connect(InetSocketAddress("127.0.0.1", 27183), 1500)
                    val writer = BufferedWriter(OutputStreamWriter(socket.getOutputStream(), Charsets.UTF_8))
                    writer.write(JSONObject().put("type", "hello").put("protocol", 2).toString())
                    writer.newLine()
                    writer.flush()
                    onConnection(true)
                    while (running && !socket.isClosed) {
                        val message = queue.poll(250, java.util.concurrent.TimeUnit.MILLISECONDS)
                        if (message != null) {
                            writer.write(message); writer.newLine(); writer.flush()
                        }
                    }
                } catch (_: Exception) {
                    onConnection(false)
                    try { Thread.sleep(800) } catch (_: InterruptedException) { }
                } finally { try { socket?.close() } catch (_: Exception) { } }
            }
            onConnection(false)
        }
    }
    fun send(message: String) {
        if (!running) return
        if (!queue.offer(message)) { queue.poll(); queue.offer(message) }
    }
    fun stop() { running = false; worker?.interrupt(); worker = null; queue.clear() }
}

private data class LocalStroke(val path: Path, val paint: Paint)

private class PenCanvasView(context: android.content.Context) : View(context) {
    private val heading = Paint(3).apply { color = Color.WHITE; textSize = 25f; typeface = android.graphics.Typeface.DEFAULT_BOLD }
    private val label = Paint(3).apply { color = Color.rgb(160, 177, 198); textSize = 14f }
    private val value = Paint(3).apply { color = Color.WHITE; textSize = 17f }
    private val board = Paint(3).apply { color = Color.rgb(250, 251, 253) }
    private val border = Paint(3).apply { color = Color.rgb(75, 94, 119); style = Paint.Style.STROKE; strokeWidth = 2f }
    private val strokes = mutableListOf<LocalStroke>()
    private var activeStroke: LocalStroke? = null
    private var pcConnected = false
    private var eventCount = 0L
    private var tool = "Move stylus on the white canvas"
    private var action = "Waiting"
    private var pressure = 0f
    private var maxPressure = 0f
    private var x = 0f
    private var y = 0f
    private var hover = false
    private var buttons = 0
    private val margin = 24f
    private val canvasTop = 154f
    private val bottom = 24f
    fun setPcLink(connected: Boolean) { pcConnected = connected; invalidate() }
    override fun onTouchEvent(event: MotionEvent): Boolean { handle(event); return true }
    override fun onGenericMotionEvent(event: MotionEvent): Boolean { handle(event); return true }

    private fun handle(e: MotionEvent) {
        if (e.pointerCount <= 0) return
        val i = e.actionIndex.coerceIn(0, e.pointerCount - 1)
        val type = e.getToolType(i)
        val toolName = when (type) {
            MotionEvent.TOOL_TYPE_STYLUS -> "STYLUS"
            MotionEvent.TOOL_TYPE_ERASER -> "ERASER"
            MotionEvent.TOOL_TYPE_FINGER -> "FINGER"
            MotionEvent.TOOL_TYPE_MOUSE -> "MOUSE"
            else -> "UNKNOWN"
        }
        val actionName = MotionEvent.actionToString(e.actionMasked)
        x = e.getX(i); y = e.getY(i); pressure = e.getPressure(i).coerceIn(0f, 1f)
        maxPressure = maxOf(maxPressure, pressure)
        tool = toolName; action = actionName; buttons = e.buttonState
        hover = e.actionMasked == MotionEvent.ACTION_HOVER_ENTER || e.actionMasked == MotionEvent.ACTION_HOVER_MOVE || e.actionMasked == MotionEvent.ACTION_HOVER_EXIT
        eventCount++
        val cw = (width - margin * 2).coerceAtLeast(1f)
        val ch = (height - canvasTop - bottom).coerceAtLeast(1f)
        val cx = (x - margin).coerceIn(0f, cw)
        val cy = (y - canvasTop).coerceIn(0f, ch)
        val drawTool = type == MotionEvent.TOOL_TYPE_STYLUS || type == MotionEvent.TOOL_TYPE_ERASER || type == MotionEvent.TOOL_TYPE_FINGER
        if (drawTool && (e.actionMasked == MotionEvent.ACTION_DOWN || e.actionMasked == MotionEvent.ACTION_POINTER_DOWN)) {
            val paint = Paint(3).apply {
                color = if (type == MotionEvent.TOOL_TYPE_ERASER) Color.WHITE else Color.rgb(20, 105, 220)
                style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
                strokeWidth = 2f + pressure * 16f
            }
            val path = Path().apply { moveTo(cx, cy) }
            activeStroke = LocalStroke(path, paint); strokes.add(activeStroke!!)
        } else if (drawTool && e.actionMasked == MotionEvent.ACTION_MOVE && activeStroke != null) {
            activeStroke!!.path.lineTo(cx, cy)
            activeStroke!!.paint.strokeWidth = 2f + pressure * 16f
        } else if (e.actionMasked == MotionEvent.ACTION_UP || e.actionMasked == MotionEvent.ACTION_POINTER_UP || e.actionMasked == MotionEvent.ACTION_CANCEL) {
            activeStroke = null
        }
        val packet = JSONObject().apply {
            put("type", "pen"); put("protocol", 2); put("tool", toolName); put("action", actionName)
            put("pointerId", e.getPointerId(i))
            put("x", x.toDouble()); put("y", y.toDouble())
            put("canvasX", cx.toDouble()); put("canvasY", cy.toDouble())
            put("canvasWidth", cw.toDouble()); put("canvasHeight", ch.toDouble())
            put("pressure", e.getPressure(i).toDouble())
            put("tilt", e.getAxisValue(MotionEvent.AXIS_TILT, i).toDouble())
            put("orientation", e.getOrientation(i).toDouble())
            put("buttons", buttons); put("hover", hover)
            put("contact", e.actionMasked == MotionEvent.ACTION_DOWN || e.actionMasked == MotionEvent.ACTION_MOVE || e.actionMasked == MotionEvent.ACTION_POINTER_DOWN)
            put("eventTime", e.eventTime)
        }
        PenLinkHolder.client?.send(packet.toString())
        invalidate()
    }

    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        c.drawColor(Color.rgb(12, 17, 27))
        c.drawText("USB PEN PRESSURE TEST", margin, 38f, heading)
        c.drawText("Draw on the white canvas. Stroke thickness follows pressure.", margin, 65f, label)
        c.drawText("PC LINK: " + (if (pcConnected) "CONNECTED" else "WAITING"), margin, 100f, value)
        c.drawText("INPUT: $tool | $action | events: $eventCount", margin, 126f, label)
        c.drawText("Pressure: %.3f   Maximum: %.3f   Buttons: %d".format(pressure, maxPressure, buttons), margin, 146f, label)
        val rect = RectF(margin, canvasTop, width - margin, height - bottom)
        c.drawRoundRect(rect, 12f, 12f, board)
        c.save(); c.clipRect(rect)
        for (stroke in strokes) c.drawPath(stroke.path, stroke.paint)
        if (hover && x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
            val cursor = Paint(3).apply { color = Color.rgb(0, 130, 220); style = Paint.Style.STROKE; strokeWidth = 2f }
            c.drawCircle(x, y, 9f, cursor)
        }
        c.restore(); c.drawRoundRect(rect, 12f, 12f, border)
    }
}
private object PenLinkHolder { var client: PenLinkClient? = null }
