import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/simulate-ad", response_class=HTMLResponse)
async def simulate_ad(dest: str = "https://example.com"):
    # Simulates a typical ad network landing page.
    # It has a timer (3 seconds) and then redirects to the destination URL.
    # It also attempts to open an annoying popup, which our bot should handle!
    html_content = f"""
    <html>
    <head>
        <title>AdMonetized Short Link</title>
        <script>
            // Attempt popup (the engine should catch and close this)
            try {{
                window.open("https://admaven.com/popup-ad", "_blank");
            }} catch(e) {{
                console.log("Popup blocked by browser or system");
            }}

            // Start countdown
            let seconds = 3;
            function countdown() {{
                seconds--;
                document.getElementById("timer").innerText = seconds;
                if (seconds <= 0) {{
                    window.location.href = "{dest}";
                }} else {{
                    setTimeout(countdown, 1000);
                }}
            }}
            window.onload = function() {{
                setTimeout(countdown, 1000);
            }}
        </script>
        <style>
            body {{
                background-color: #0f0c20;
                color: #ffffff;
                font-family: sans-serif;
                text-align: center;
                padding-top: 100px;
            }}
            .container {{
                max-width: 500px;
                margin: 0 auto;
                padding: 40px;
                border: 1px solid #332a63;
                border-radius: 8px;
                background-color: #15102a;
            }}
            .timer {{
                font-size: 48px;
                color: #7b2cbf;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Preparing your destination link...</h2>
            <p>You will be redirected automatically in:</p>
            <div class="timer" id="timer">3</div>
            <p>Sponsored by Lumina Ad Simulator</p>
        </div>
    </body>
    </html>
    """
    return html_content

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
