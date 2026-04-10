from flask import Flask, render_template, Response, stream_with_context
from network.diagnostics import run_analysis_stream

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze/stream")
def analyze_stream():
    def generate():
        yield from run_analysis_stream()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=8000)
