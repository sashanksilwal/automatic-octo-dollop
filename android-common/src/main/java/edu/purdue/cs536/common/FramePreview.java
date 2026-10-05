package edu.purdue.cs536.common;

import android.content.Context;
import android.graphics.*;
import android.view.View;
import edu.purdue.cs536.stream.Frame;

/** UI-thread-owned bitmap. Receiver polls the latest frame instead of queuing UI work. */
public final class FramePreview extends View {
    private Bitmap bitmap;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private String message = "Waiting for video";
    public FramePreview(Context context) { super(context); setContentDescription("Live glasses camera preview"); }
    public boolean show(Frame frame) {
        BitmapFactory.Options bounds = new BitmapFactory.Options(); bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(frame.jpeg, 0, frame.jpeg.length, bounds);
        if (bounds.outWidth < 1 || bounds.outHeight < 1 || bounds.outWidth > 4096 || bounds.outHeight > 4096
                || (long) bounds.outWidth * bounds.outHeight > 8_000_000L) { clear("Invalid image dimensions"); return false; }
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inPreferredConfig = Bitmap.Config.RGB_565;
        options.inSampleSize = Math.max(1, Math.max(bounds.outWidth / 1280, bounds.outHeight / 720));
        Bitmap next = BitmapFactory.decodeByteArray(frame.jpeg, 0, frame.jpeg.length, options);
        if (next == null) { clear("Cannot decode image"); return false; }
        if (bitmap != null) bitmap.recycle(); bitmap = next; invalidate(); return true;
    }
    public void clear(String message) {
        this.message = message;
        if (bitmap != null) { bitmap.recycle(); bitmap = null; } invalidate();
    }
    @Override protected void onDraw(Canvas canvas) {
        canvas.drawColor(Color.BLACK);
        if (bitmap != null) {
            float scale = Math.min((float) getWidth() / bitmap.getWidth(), (float) getHeight() / bitmap.getHeight());
            float w = bitmap.getWidth() * scale, h = bitmap.getHeight() * scale;
            canvas.drawBitmap(bitmap, null, new RectF((getWidth()-w)/2, (getHeight()-h)/2, (getWidth()+w)/2, (getHeight()+h)/2), paint);
        } else {
            paint.setColor(Color.LTGRAY); paint.setTextSize(15 * getResources().getDisplayMetrics().scaledDensity);
            paint.setTextAlign(Paint.Align.CENTER); canvas.drawText(message, getWidth()/2f, getHeight()/2f, paint);
        }
    }
}
