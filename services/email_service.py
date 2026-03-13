import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app


def _get_smtp_connection():
    """Create an SMTP connection based on app config."""
    host = current_app.config.get('SMTP_HOST', 'localhost')
    port = current_app.config.get('SMTP_PORT', 465)
    use_ssl = current_app.config.get('SMTP_USE_SSL', True)
    use_tls = current_app.config.get('SMTP_USE_TLS', False)
    username = current_app.config.get('SMTP_USERNAME', '')
    password = current_app.config.get('SMTP_PASSWORD', '')

    context = ssl.create_default_context()

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=10, context=context)
    elif use_tls:
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls(context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=10)

    if username and password:
        server.login(username, password)

    return server


def _send_email(to_email, subject, html_body):
    """Send an email using SMTP config."""
    from_email = current_app.config.get('SMTP_FROM_EMAIL', 'noreply@voicelink.local')
    from_name = current_app.config.get('SMTP_FROM_NAME', 'VoiceLink')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{from_name} <{from_email}>'
    msg['To'] = to_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = _get_smtp_connection()
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send email to {to_email}: {e}')
        return False


def send_verification_email(user, token):
    """Send email verification link to a user."""
    base_url = current_app.config.get('APP_URL', 'https://10.10.23.68')
    verify_url = f'{base_url}/verify-email?token={token}'

    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #174DA4; margin: 0;">VoiceLink</h1>
        </div>
        <div style="background: #fff; border: 1px solid #e0e0e0; padding: 32px;">
            <h2 style="margin-top: 0; color: #1A1D21;">Verify Your Email</h2>
            <p style="color: #5A6270; line-height: 1.6;">
                Hi <strong>{user.display_name}</strong>,
            </p>
            <p style="color: #5A6270; line-height: 1.6;">
                Your account has been approved. Please verify your email address
                by clicking the button below to access VoiceLink.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{verify_url}"
                   style="background: #174DA4; color: #fff; padding: 12px 32px;
                          text-decoration: none; font-weight: 600; display: inline-block;">
                    Verify Email Address
                </a>
            </div>
            <p style="color: #8C939D; font-size: 13px;">
                If the button doesn't work, copy and paste this link into your browser:<br>
                <a href="{verify_url}" style="color: #174DA4; word-break: break-all;">{verify_url}</a>
            </p>
            <p style="color: #8C939D; font-size: 13px;">
                This link expires in 48 hours.
            </p>
        </div>
        <p style="color: #8C939D; font-size: 12px; text-align: center; margin-top: 16px;">
            VoiceLink &mdash; Local Network Communication Platform
        </p>
    </div>
    """

    return _send_email(user.email, 'Verify Your Email - VoiceLink', html)


def send_password_reset_email(user, token):
    """Send password reset link to a user."""
    base_url = current_app.config.get('APP_URL', 'https://10.10.23.68')
    reset_url = f'{base_url}/reset-password?token={token}'

    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #174DA4; margin: 0;">VoiceLink</h1>
        </div>
        <div style="background: #fff; border: 1px solid #e0e0e0; padding: 32px;">
            <h2 style="margin-top: 0; color: #1A1D21;">Reset Your Password</h2>
            <p style="color: #5A6270; line-height: 1.6;">
                Hi <strong>{user.display_name}</strong>,
            </p>
            <p style="color: #5A6270; line-height: 1.6;">
                A password reset was requested for your account. Click the button
                below to set a new password.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{reset_url}"
                   style="background: #174DA4; color: #fff; padding: 12px 32px;
                          text-decoration: none; font-weight: 600; display: inline-block;">
                    Reset Password
                </a>
            </div>
            <p style="color: #8C939D; font-size: 13px;">
                If the button doesn't work, copy and paste this link into your browser:<br>
                <a href="{reset_url}" style="color: #174DA4; word-break: break-all;">{reset_url}</a>
            </p>
            <p style="color: #8C939D; font-size: 13px;">
                This link expires in 1 hour. If you didn't request this, ignore this email.
            </p>
        </div>
        <p style="color: #8C939D; font-size: 12px; text-align: center; margin-top: 16px;">
            VoiceLink &mdash; Local Network Communication Platform
        </p>
    </div>
    """

    return _send_email(user.email, 'Reset Your Password - VoiceLink', html)
