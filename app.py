from src import create_app
from flask import Flask, render_template
from src.routes.order_routes import bp as order_bp

app = create_app()
app.register_blueprint(order_bp)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    # Windows 환경에서 host/port를 명시하는 게 편함
    
    
    app.run(host="0.0.0.0", port=5000, debug=True)
