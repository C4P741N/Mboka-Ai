
import html
from typing import Dict

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
INK = "#16232E"      # headings
BODY = "#526070"     # body copy
MUTED = "#97A2AC"     # dividers, empty-state text
BORDER = "#E3E8ED"    # card border
ACCENT = "#0F766E"    # apply buttons (the one accent color)

def _render_apply_buttons(apply_options: Dict[str, str]) -> str:
    """Render one styled button per apply option. Each option needs 'title' and 'url'."""
    if not apply_options:
        return (
            f'<p style="margin:0; color:{MUTED}; font-size:13px; '
            'font-style:italic;">No application links available</p>'
        )
 
    buttons = []
    for option in apply_options:
        title = html.escape(str(option.get("title") or "Apply now"))
        url = html.escape(str(option.get("url") or "#"), quote=True)
        buttons.append(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block; padding:10px 16px; '
            f'margin:0 8px 8px 0; background:{ACCENT}; color:#ffffff; '
            'text-decoration:none; border-radius:6px; font-size:14px; '
            f'font-weight:600; font-family:{FONT};">'
            f'{title}</a>'
        )
    return "".join(buttons)
 
 
def render_job_card(job: Dict[str, str]) -> str:
    """
    Render a single job posting as a styled HTML card.
 
    `job["apply_options"]` should be a list of dicts shaped like:
        [{"title": "Apply on LinkedIn", "url": "https://..."},
         {"title": "Apply on company site", "url": "https://..."}]
 
    Missing fields and an empty/absent apply_options list degrade
    gracefully so a malformed job entry never breaks the layout.
    """
    title = html.escape(str(job.get("title") or "Untitled position"))
    company = html.escape(str(job.get("company") or ""))
    location = html.escape(str(job.get("location") or ""))
    description = html.escape(str(job.get("description") or "")).replace("\n", "<br>")
 
    meta_parts = []
    if company:
        meta_parts.append(f'<strong style="color:{INK};">{company}</strong>')
    if location:
        meta_parts.append(f'<span>\U0001F4CD {location}</span>')
 
    meta_html = ""
    if meta_parts:
        divider = f'<span style="color:{MUTED}; margin:0 8px;">&middot;</span>'
        meta_html = (
            f'<p style="margin:0 0 14px 0; color:{BODY}; font-size:14px;">'
            f'{divider.join(meta_parts)}</p>'
        )
 
    options = job.get("apply_options") or job.get("source_link")

    apply_buttons = _render_apply_buttons(options)
 
    return f"""
    <div style="
        width:100%;
        max-width:640px;
        box-sizing:border-box;
        border:1px solid {BORDER};
        border-radius:10px;
        padding:24px;
        margin-bottom:20px;
        background:#ffffff;
        font-family:{FONT};
        box-shadow:0 1px 2px rgba(22,35,46,0.04), 0 1px 6px rgba(22,35,46,0.05);
    ">
        <h2 style="margin:0 0 8px 0; color:{INK}; font-size:19px; font-weight:700; line-height:1.3;">
            {title}
        </h2>
 
        {meta_html}
 
        <p style="
            margin:0 0 18px 0;
            color:{BODY};
            font-size:14px;
            line-height:1.6;
            display:-webkit-box;
            -webkit-line-clamp:3;
            -webkit-box-orient:vertical;
            overflow:hidden;
            text-overflow:ellipsis;
            word-break:break-word;
        ">
            {description}
        </p>
 
        <div>
            {apply_buttons}
        </div>
    </div>
    """

def render_email(job_cards):
    return f"""
    <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    padding: 20px;
                }}

                .container {{
                    max-width: 700px;
                    margin: auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                }}

                h1 {{
                    color: #333;
                }}

                p {{
                    color: #555;
                    line-height: 1.6;
                }}
            </style>
        </head>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    padding: 20px;
                }}

                .container {{
                    max-width: 700px;
                    margin: auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                }}

                h1 {{
                    color: #333;
                }}

                p {{
                    color: #555;
                    line-height: 1.6;
                }}
            </style>
        </head>

        <body>

            <div class="container">

            <p>Your excellency, we found the following jobs that may interest you.</p>

            {job_cards}

            <hr>

            <p style="font-size:12px;color:#888;">
            You're receiving this email because you subscribed to job alerts.
            </p>

            </div>

        </body>
    </html>
"""