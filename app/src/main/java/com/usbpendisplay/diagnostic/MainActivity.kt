package com.usbpendisplay.diagnostic

import android.app.Activity
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface

class MainActivity : Activity() {
    private lateinit var panel: PenDiagnosticView
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        panel = PenDiagnosticView(this)
        window.statusBarColor = Color.rgb(12, 17, 27)
        window.navigationBarColor = Color.rgb(12, 17, 27)
        setContentView(panel)
    }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        panel.updateFrom(event)
        return true
    }
    override fun onGenericMotionEvent(event: MotionEvent): Boolean {
        panel.updateFrom(event)
        return true
    }
}

private class PenDiagnosticView(context: android.content.Context) : View(context) {
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
        invalidate()
    }

    override fun onDraw(c: Canvas) {
        super.onDraw(c)
        val p = 28f
        var yText = 55f
        c.drawText("USB PEN DISPLAY", p, yText, heading); yText += 32f
        c.drawText("Build 0.1.0  •  Stylus input diagnostic", p, yText, muted); yText += 28f
        c.drawLine(p, yText, width - p, yText, line); yText += 36f
        val state = if (!received) "WAITING" else if (contact) "CONTACT" else if (hover) "HOVER" else "INPUT"
        c.drawText("INPUT STATUS: $state", p, yText, heading); yText += 36f
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
            yText += 31f
        }
        val top = yText + 10f
        val bottom = height - 55f
        if (bottom > top + 80f) {
            c.drawLine(p, top, width - p, top, line)
            c.drawText("DRAWING AREA — move the pen here", p, top + 27f, muted)
            c.drawRect(p, top + 42f, width - p, bottom, line)
            if (received) c.drawCircle(x.coerceIn(p, width - p), y.coerceIn(top + 42f, bottom), 7f + pressure.coerceIn(0f, 1f) * 12f, dot)
        }
        c.drawText("Finger input is labelled separately from stylus input.", p, height - 22f, muted)
    }
}
