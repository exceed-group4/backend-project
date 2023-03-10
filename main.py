from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import hashlib, uuid
import os
import requests
load_dotenv(".env")

user = os.getenv("user")
password = os.getenv("password")

client = MongoClient(f"mongodb://{user}:{password}@mongo.exceed19.online:8443/?authMechanism=DEFAULT")
db = client["exceed04"]
collection = db["Safe"]
token = os.getenv("token")

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

class Safe(BaseModel):
    safe_id: int
    safe_name: str
    safe_pin: str
    min_temp: int
    max_temp: int
    min_humid: int
    max_humid: int

class Password(BaseModel):
    safe_id: int
    safe_pin: str

class Update(BaseModel):
    safe_id: int
    #safe_name: str
    safe_pin: str
    lock: bool
    safe_system_available: bool

class alerts(BaseModel):
    safe_id : int 
    flame_alert : int 
    humid_alert : int 
    temp_alert : int 
    ultrasonic_alert : int 

def hash_password(password):
    salt = uuid.uuid4().hex
    ph = (password + salt).encode("utf-8")
    hashed_password = hashlib.sha512(ph).hexdigest()
    return hashed_password, salt

def check_password(password, hashed_password, salt):
    ph = (password + salt).encode("utf-8")
    hashed_password1 = hashlib.sha512(ph).hexdigest()
    return hashed_password1 == hashed_password

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/safe")
def get_safe():
    results = []
    cursor = collection.find({}, {"_id": 0})
    for document in cursor:
        results.append(document)
    return results

@app.post("/new_safe")
def new_safe(safe: Safe):
    safe_id = safe.safe_id
    safe_name = safe.safe_name
    safe_pin = safe.safe_pin
    if collection.find_one({"safe_id": safe_id}):
        raise HTTPException(status_code=400, detail="safe_id already exists")
    hashed_pin,salt = hash_password(safe_pin)
    new_safe = {
        "safe_id": safe_id,
        "safe_name": safe_name,
        "safe_pin": hashed_pin,
        "salt": salt,
        "connected": False,
        "safe_system_available": False,
        "min_temp": safe.min_temp,
        "max_temp": safe.max_temp,
        "min_humid": safe.min_humid,
        "max_humid": safe.max_humid,
        "flame_alert": False,
        "humid_alert": False,
        "temp_alert": False,
        "ultrasonic_alert": False,
        "locked": False
    }
    collection.insert_one(new_safe)
    return {"detail": "add new safe success"}

@app.put("/password")
def ch_password(password: Password):
    safe_id = password.safe_id
    safe_pin = password.safe_pin
    safe = collection.find_one({"safe_id": safe_id})
    if safe is None or not check_password(safe_pin,safe["safe_pin"],safe["salt"]):
        raise HTTPException(status_code=400, detail="safe_id or safe_pin is incorrect")
    return {"detail": "access success"}

@app.put("/safe_update")
def safe_update(update: Update):
    safe_id = update.safe_id
    #safe_name = update.safe_name
    safe_pin = update.safe_pin
    lock = update.lock
    safe_system_available = update.safe_system_available
    safe = collection.find_one({"safe_id": safe_id})
    #if safe is None or not check_password(safe_pin,safe["safe_pin"],safe["salt"]): #or safe["safe_name"] != safe_name:
    #    raise HTTPException(status_code=400, detail="safe_id or safe_pin is incorrect")
    collection.update_one({"safe_id": safe_id}, {"$set": {"locked": lock, "safe_system_available": safe_system_available}})
    return {"detail": "update success"}
    
@app.get("/status/{safe_id}")
def get_status(safe_id:int):
    status = collection.find_one({"safe_id":safe_id},{"_id":0})
    return status 

@app.put("/alert")
def put_alert(ale : alerts):
    filter = {"safe_id":ale.safe_id}
    newvalues = {"$set" :{"flame_alert":bool(ale.flame_alert),"humid_alert":bool(ale.humid_alert),"temp_alert":bool(ale.temp_alert),"ultrasonic_alert":bool(ale.ultrasonic_alert)}}
    collection.update_one(filter,newvalues)
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'content-type':
        'application/x-www-form-urlencoded',
        'Authorization':'Bearer '+token
    }
    msg = "Alert from Safe "+str(ale.safe_id)+"\n"
    if ale.flame_alert == 1:
        msg += "Flame Alert\n"
    if ale.humid_alert == 1:
        msg += "Humid Alert\n"
    if ale.temp_alert == 1:
        msg += "Temp Alert\n"
    if ale.ultrasonic_alert == 1:
        msg += "Ultrasonic Alert\n"
    r = requests.post(url, headers=headers , data = {'message':msg})
    return {"detail": "alert success"}