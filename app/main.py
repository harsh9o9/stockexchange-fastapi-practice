from . import models
import yfinance
from fastapi import BackgroundTasks, FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from .database import SessionLocal, engine
from pydantic import BaseModel
from .models import Stock
from sqlalchemy.orm import Session
from pydantic import BaseModel

app = FastAPI()
models.Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="app/templates")


class StockRequest(BaseModel):
    symbol: str


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def fetch_stock_data(id: int):
    db = SessionLocal()
    stock = db.query(Stock).filter(Stock.id == id).first()

    yahoo_data = yfinance.Ticker(stock.symbol)

    stock.ma200 = yahoo_data.info["twoHundredDayAverage"]
    stock.ma50 = yahoo_data.info["fiftyDayAverage"]
    stock.price = yahoo_data.info["previousClose"]
    stock.forward_pe = yahoo_data.info["forwardPE"]
    stock.forward_eps = yahoo_data.info["forwardEps"]
    if "dividendYield" in yahoo_data.info:
        stock.dividend_yield = yahoo_data.info["dividendYield"] * 100

    db.add(stock)
    db.commit()


@app.get("/")
def home(
    request: Request,
    forward_pe=None,
    dividend_yield=None,
    ma50=None,
    ma200=None,
    db: Session = Depends(get_db),
):
    """
    Retrieves the home page.

    Parameters:
                                                                                                request (Request): The incoming request.

    Returns:
                                                    TemplateResponse: The response containing the rendered home page.
    """

    stocks = db.query(Stock)

    if forward_pe:
        stocks = stocks.filter(Stock.forward_pe < forward_pe)

    if dividend_yield:
        stocks = stocks.filter(Stock.dividend_yield > dividend_yield)

    if ma50:
        stocks = stocks.filter(Stock.price > Stock.ma50)

    if ma200:
        stocks = stocks.filter(Stock.price > Stock.ma200)

    stocks = stocks.all()

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "stocks": stocks,
            "dividend_yield": dividend_yield,
            "forward_pe": forward_pe,
            "ma200": ma200,
            "ma50": ma50,
        },
    )


@app.post("/stock")
async def create_stocks(
    stock_request: StockRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a new stock.
    This function is an HTTP POST endpoint that creates a new stock. It is mapped to the "/stocks" URL.

    Returns:
                                                                                                                                    A dictionary with a single key-value pair, where the key is "stocks" and the value is "Hello World".
    """

    stock = Stock()
    stock.symbol = stock_request.symbol
    db.add(stock)
    db.commit()

    background_tasks.add_task(fetch_stock_data, stock.id)

    return {"code": "success", "message": "stock was added to the database"}
