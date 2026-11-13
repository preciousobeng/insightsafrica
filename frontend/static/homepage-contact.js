  async function submitContact(e) {
    e.preventDefault();
    var btn = document.getElementById('cf-btn');
    var fb  = document.getElementById('cf-feedback');
    btn.disabled = true;
    btn.textContent = 'Sending\u2026';
    fb.className = 'cform-msg';
    fb.textContent = '';

    var payload = {
      name:         document.getElementById('cf-name').value.trim(),
      email:        document.getElementById('cf-email').value.trim(),
      enquiry_type: document.getElementById('cf-type').value,
      message:      document.getElementById('cf-msg').value.trim()
    };

    try {
      var res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      var data = null;
      try { data = await res.json(); } catch (e) { data = null; }
      if (res.ok && data && data.ok) {
        fb.className = 'cform-msg ok';
        fb.textContent = "Message sent \u2014 we'll be in touch shortly.";
        document.getElementById('contact-form').reset();
      } else {
        fb.className = 'cform-msg err';
        fb.textContent = (data && data.detail) ? data.detail
          : 'Sorry, we could not send your message right now. Please email us directly at info@insightsafrica.org.';
      }
    } catch (err) {
      fb.className = 'cform-msg err';
      fb.textContent = 'Network error. Please try again, or email us directly at info@insightsafrica.org.';
    }

    btn.disabled = false;
    btn.textContent = 'Send message \u2192';
  }
document.querySelector("#contact-form").addEventListener("submit",submitContact);
