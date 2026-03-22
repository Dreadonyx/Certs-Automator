from flask import Flask, render_template, request, send_file, jsonify, Response, stream_with_context
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
import csv
import zipfile
import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs('uploads', exist_ok=True)

FONT_MAP = {
    'arial.ttf':   '/usr/share/fonts/noto/NotoSans-Regular.ttf',
    'georgia.ttf': '/usr/share/fonts/noto/NotoSerif-Regular.ttf',
    'times.ttf':   '/usr/share/fonts/noto/NotoSerif-Regular.ttf',
}

IMAGE_FORMATS = {
    'image/png':  ('PNG',  'png'),
    'image/jpeg': ('JPEG', 'jpg'),
    'image/jpg':  ('JPEG', 'jpg'),
    'image/webp': ('WEBP', 'webp'),
    'image/bmp':  ('BMP',  'bmp'),
    'image/tiff': ('TIFF', 'tiff'),
    'image/gif':  ('GIF',  'gif'),
}

EXPORT_FORMAT_MAP = {
    'png':  ('PNG',  'png'),
    'jpg':  ('JPEG', 'jpg'),
    'webp': ('WEBP', 'webp'),
    'pdf':  ('PDF',  'pdf'),
}

SMTP_PRESETS = {
    'gmail':   ('smtp.gmail.com', 587),
    'outlook': ('smtp-mail.outlook.com', 587),
    'yahoo':   ('smtp.mail.yahoo.com', 587),
    'zoho':    ('smtp.zoho.com', 587),
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def load_font(font_family, size):
    font_path = FONT_MAP.get(font_family, font_family)
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        try:
            return ImageFont.truetype('/usr/share/fonts/noto/NotoSans-Regular.ttf', size)
        except OSError:
            return ImageFont.load_default(size=size)


def decode_template(template_data):
    """Decode base64 data-URL → (PIL Image, pil_format, extension)."""
    header, raw = template_data.split(',', 1)
    mime = header.split(':')[1].split(';')[0].lower()
    pil_format, ext = IMAGE_FORMATS.get(mime, ('PNG', 'png'))
    image = Image.open(io.BytesIO(base64.b64decode(raw)))
    if pil_format == 'JPEG' and image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    return image, pil_format, ext


def draw_certificate(template_image, name, department, settings):
    """Overlay name + department text on a copy of the template."""
    cert = template_image.copy()
    draw = ImageDraw.Draw(cert)

    name_font = load_font(settings.get('nameFont', 'arial.ttf'), int(settings.get('nameFontSize', 38)))
    dept_font = load_font(settings.get('deptFont', 'arial.ttf'), int(settings.get('deptFontSize', 32)))

    draw.text(
        (int(settings.get('nameX', 420)), int(settings.get('nameY', 270))),
        name, fill=hex_to_rgb(settings.get('nameColor', '#000000')), font=name_font,
    )
    draw.text(
        (int(settings.get('deptX', 76)), int(settings.get('deptY', 303))),
        department, fill=hex_to_rgb(settings.get('deptColor', '#000000')), font=dept_font,
    )
    return cert


def image_to_bytes(image, pil_format):
    buf = io.BytesIO()
    if pil_format in ('JPEG', 'PDF') and image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    image.save(buf, pil_format)
    return buf.getvalue()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/parse-csv', methods=['POST'])
def parse_csv():
    """Parse CSV → [{name, department, email}, …]"""
    try:
        if 'csvFile' not in request.files or request.files['csvFile'].filename == '':
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        stream = io.StringIO(request.files['csvFile'].stream.read().decode('UTF8'), newline=None)
        rows = list(csv.reader(stream))

        # Auto-detect header row
        if rows and rows[0] and rows[0][0].strip().lower() in ('name', 'participant'):
            rows = rows[1:]

        participants = []
        for row in rows:
            if row and row[0].strip():
                participants.append({
                    'name':       row[0].strip(),
                    'department': row[1].strip() if len(row) > 1 else '',
                    'email':      row[2].strip() if len(row) > 2 else '',
                })

        return jsonify({'success': True, 'participants': participants, 'count': len(participants)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/generate', methods=['POST'])
def generate_certificate():
    """Generate a single certificate (for preview). Returns base64 image."""
    try:
        data = request.json
        template_image, pil_format, ext = decode_template(data['template'])
        cert = draw_certificate(template_image, data.get('name', ''), data.get('department', ''), data)
        img_bytes = image_to_bytes(cert, pil_format)
        mime = 'image/jpeg' if ext == 'jpg' else f'image/{ext}'
        return jsonify({
            'success': True,
            'image': f'data:{mime};base64,{base64.b64encode(img_bytes).decode()}',
            'ext': ext,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/generate-batch', methods=['POST'])
def generate_batch():
    """Batch generate → merged PDF or ZIP depending on exportFormat."""
    try:
        data = request.json
        template_image, default_fmt, default_ext = decode_template(data['template'])
        participants = data.get('participants', [])
        settings = data.get('settings', {})

        export_fmt = settings.get('exportFormat', 'same')
        pil_format, ext = EXPORT_FORMAT_MAP.get(export_fmt, (default_fmt, default_ext))

        certs = []
        for p in participants:
            c = draw_certificate(template_image, p['name'], p.get('department', ''), settings)
            if pil_format in ('JPEG', 'PDF') and c.mode in ('RGBA', 'P'):
                c = c.convert('RGB')
            certs.append(c)

        if pil_format == 'PDF':
            buf = io.BytesIO()
            if certs:
                certs[0].save(buf, 'PDF', save_all=True, append_images=certs[1:])
            buf.seek(0)
            return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='certificates.pdf')

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p, c in zip(participants, certs):
                zf.writestr(f"{p['name'].replace(' ', '_')}_certificate.{ext}", image_to_bytes(c, pil_format))
        buf.seek(0)
        return send_file(buf, mimetype='application/zip', as_attachment=True, download_name='certificates.zip')

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/send-certificates', methods=['POST'])
def send_certificates():
    """Generate + email each certificate. Streams SSE progress events."""
    data = request.json

    template_image, pil_format, ext = decode_template(data['template'])
    participants = data.get('participants', [])
    settings = data.get('settings', {})

    # SMTP config
    provider = data.get('smtpProvider', 'custom')
    if provider in SMTP_PRESETS:
        smtp_host, smtp_port = SMTP_PRESETS[provider]
    else:
        smtp_host = data.get('smtpHost', '')
        smtp_port = int(data.get('smtpPort', 587))

    smtp_user = data.get('smtpUser', '')
    smtp_pass = data.get('smtpPass', '')
    from_name = data.get('fromName', 'CertFlow')
    subject   = data.get('emailSubject', 'Your Certificate')
    body      = data.get('emailBody', 'Hi {name},\n\nPlease find your certificate attached.\n\nRegards,\nCertFlow')

    export_fmt = settings.get('exportFormat', 'same')
    out_fmt, out_ext = EXPORT_FORMAT_MAP.get(export_fmt, (pil_format, ext))
    if out_fmt == 'PDF':
        out_fmt, out_ext = pil_format, ext  # PDF doesn't make sense per-attachment here; use image format

    def stream():
        results = []
        skipped = 0

        try:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'SMTP connection failed: {e}'})}\n\n"
            return

        total = len([p for p in participants if p.get('email')])

        for i, p in enumerate(participants):
            email_addr = p.get('email', '').strip()
            if not email_addr:
                skipped += 1
                yield f"data: {json.dumps({'type': 'skip', 'name': p['name'], 'reason': 'no email'})}\n\n"
                continue

            try:
                cert = draw_certificate(template_image, p['name'], p.get('department', ''), settings)
                cert_bytes = image_to_bytes(cert, out_fmt)

                personal_body = body.replace('{name}', p['name']).replace('{department}', p.get('department', ''))

                msg = MIMEMultipart()
                msg['From']    = f'{from_name} <{smtp_user}>'
                msg['To']      = email_addr
                msg['Subject'] = subject.replace('{name}', p['name'])
                msg.attach(MIMEText(personal_body, 'plain'))

                filename = f"{p['name'].replace(' ', '_')}_certificate.{out_ext}"
                attachment = MIMEApplication(cert_bytes, Name=filename)
                attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(attachment)

                server.sendmail(smtp_user, email_addr, msg.as_string())
                results.append({'name': p['name'], 'status': 'sent'})
                yield f"data: {json.dumps({'type': 'sent', 'name': p['name'], 'email': email_addr, 'index': i+1, 'total': total})}\n\n"

            except Exception as e:
                results.append({'name': p['name'], 'status': 'failed', 'reason': str(e)})
                yield f"data: {json.dumps({'type': 'failed', 'name': p['name'], 'email': email_addr, 'reason': str(e)})}\n\n"

        try:
            server.quit()
        except Exception:
            pass

        sent  = sum(1 for r in results if r['status'] == 'sent')
        failed = sum(1 for r in results if r['status'] == 'failed')
        yield f"data: {json.dumps({'type': 'done', 'sent': sent, 'failed': failed, 'skipped': skipped})}\n\n"

    return Response(stream_with_context(stream()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
