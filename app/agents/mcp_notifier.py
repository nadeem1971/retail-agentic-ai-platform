from app.config import PROJECT_ID, SENDGRID_API_KEY, NOTIFICATION_EMAIL
from google.cloud import bigquery, firestore
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import datetime, timezone
import uuid

bq = bigquery.Client(project=PROJECT_ID)
db = firestore.Client(project=PROJECT_ID, database="default")


def check_gdpr_consent(session_id: str) -> bool:
    """Check if customer has consented to email notifications"""
    try:
        doc = db.collection("consent").document(session_id).get()
        if doc.exists:
            return doc.to_dict().get("email_consent", False)
        return False
    except Exception as e:
        print(f"[MCP] Consent check error: {e}")
        return False


def grant_consent(session_id: str, email: str):
    """Record customer email consent in Firestore"""
    db.collection("consent").document(session_id).set({
        "email":         email,
        "email_consent": True,
        "consented_at":  datetime.now(timezone.utc),
        "gdpr_version":  "1.0"
    })


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send email via SendGrid"""
    if not SENDGRID_API_KEY:
        print("[MCP] No SendGrid API key — email not sent")
        return False
    try:
        message = Mail(
            from_email="nadeem.ahmad.arch@gmail.com",
            to_emails="nadeem.ahmad.arch@gmail.com",
            subject=subject,
            html_content=html_content
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"[MCP] Email sent to {to_email} — status: {response.status_code}")
        return response.status_code in [200, 202]
    except Exception as e:
        print(f"[MCP] SendGrid error: {e}")
        return False


def log_notification(event_type: str, session_id: str,
                     message: str, metadata: dict, email_sent: bool):
    """Log all notifications to BigQuery"""
    rows = [{
        "notification_id": str(uuid.uuid4()),
        "event_type":      event_type,
        "session_id":      session_id,
        "message":         message,
        "metadata":        str(metadata or {}),
        "status":          "sent" if email_sent else "logged_only",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }]
    try:
        bq.insert_rows_json(f"{PROJECT_ID}.retail_mvp.notifications", rows)
    except Exception as e:
        print(f"[MCP] BigQuery log error: {e}")


def notify_hitl_raised(session_id: str, event_id: str, risk_score: float):
    """Alert reviewer when HITL is triggered"""
    subject = f"⚠️ HITL Review Required — Risk Score {risk_score:.2f}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#0D1B2A;padding:20px;border-radius:8px 8px 0 0">
        <h2 style="color:#C9993F;margin:0">Retail AI Platform — HITL Alert</h2>
      </div>
      <div style="background:#FEF3C7;padding:20px;border-left:4px solid #F59E0B">
        <h3 style="color:#92400E;margin:0 0 10px">⚠️ High Risk Transaction Flagged</h3>
        <p><b>Session ID:</b> {session_id}</p>
        <p><b>Event ID:</b> {event_id}</p>
        <p><b>Risk Score:</b> {risk_score:.2f} / 1.00</p>
        <p><b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
      </div>
      <div style="background:#fff;padding:20px;border:1px solid #E5E7EB">
        <p>Please review and approve or reject this transaction:</p>
        <a href="https://retail-ai-api-240442120401.asia-south1.run.app/hitl/approve/{event_id}"
           style="background:#059669;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;margin-right:10px">
           ✅ Approve
        </a>
        <a href="https://retail-ai-api-240442120401.asia-south1.run.app/hitl/reject/{event_id}"
           style="background:#DC2626;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none">
           ❌ Reject
        </a>
      </div>
      <div style="background:#F3F4F6;padding:10px 20px;font-size:11px;color:#6B7280">
        Retail AI Platform · Cloud Run asia-south1 · GDPR compliant
      </div>
    </div>
    """
    email_sent = send_email(NOTIFICATION_EMAIL, subject, html)
    log_notification("hitl_raised", session_id,
                     f"HITL review required. Risk: {risk_score:.2f}. Event: {event_id}",
                     {"event_id": event_id, "risk_score": risk_score}, email_sent)


def notify_order_confirmed(session_id: str, cart_total: float,
                           customer_email: str = None):
    """Send order confirmation to customer"""
    if customer_email and check_gdpr_consent(session_id):
        subject = "✅ Your Order is Confirmed — Retail AI Platform"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#0D1B2A;padding:20px;border-radius:8px 8px 0 0">
            <h2 style="color:#C9993F;margin:0">Order Confirmed!</h2>
          </div>
          <div style="background:#ECFDF5;padding:20px;border-left:4px solid #059669">
            <h3 style="color:#065F46">Thank you for your order</h3>
            <p><b>Order Total:</b> ₹{cart_total:.0f}</p>
            <p><b>Delivery:</b> 3-5 business days</p>
            <p><b>Session:</b> {session_id}</p>
          </div>
          <div style="background:#F3F4F6;padding:10px 20px;font-size:11px;color:#6B7280">
            To unsubscribe from order emails, reply with UNSUBSCRIBE.
          </div>
        </div>
        """
        email_sent = send_email(customer_email, subject, html)
    else:
        email_sent = False

    log_notification("order_confirmed", session_id,
                     f"Order confirmed. Total: Rs.{cart_total:.0f}",
                     {"cart_total": cart_total}, email_sent)


def notify_abandoned_cart(session_id: str, cart_total: float,
                          customer_email: str = None):
    """Send abandoned cart reminder to customer"""
    if customer_email and check_gdpr_consent(session_id):
        subject = "🛒 You left something behind — Retail AI Platform"
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#0D1B2A;padding:20px;border-radius:8px 8px 0 0">
            <h2 style="color:#C9993F;margin:0">Your cart is waiting!</h2>
          </div>
          <div style="background:#EFF6FF;padding:20px;border-left:4px solid #185FA5">
            <h3 style="color:#1E3A5F">You left ₹{cart_total:.0f} in your cart</h3>
            <p>Come back and complete your purchase before items sell out.</p>
          </div>
          <div style="background:#F3F4F6;padding:10px 20px;font-size:11px;color:#6B7280">
            To unsubscribe from cart reminders, reply with UNSUBSCRIBE.
          </div>
        </div>
        """
        email_sent = send_email(customer_email, subject, html)
    else:
        email_sent = False

    log_notification("abandoned_cart", session_id,
                     f"Cart abandoned. Total: Rs.{cart_total:.0f}",
                     {"cart_total": cart_total}, email_sent)
