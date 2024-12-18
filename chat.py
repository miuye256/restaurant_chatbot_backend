from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
import re
from openai import OpenAI
from db import  get_db, Chat, Message
from model import ChatMessageInput
from config import OPENAI_API_KEY
from function_calling import get_menu_info_from_db, get_all_menus, get_all_menu_details

router = APIRouter()

client = OpenAI(api_key=OPENAI_API_KEY)

def split_sentence(content: str):
    pattern = r'([。、!?！？])'
    parts = re.split(pattern, content)
    sentences = []
    current_sentence = ''
    for part in parts:
        current_sentence += part
        if re.match(pattern, part):
            sentences.append(current_sentence)
            current_sentence = ''
    if current_sentence:
        sentences.append(current_sentence)
    return sentences

def stream_json_res(obj: any) -> str:
    return f"{json.dumps(obj, ensure_ascii=False)}\n"

async def chat_stream(response_text: str, chat_id: str, db: Session):
    splited_content = split_sentence(response_text)
    full_content = response_text
    for sentence in splited_content:
        yield stream_json_res({'content': sentence})
    db_message = Message(chat_id=chat_id, role="assistant", content=full_content)
    db.add(db_message)
    db.commit()
    yield stream_json_res({'status': 'finished'})

@router.post("/start_chat")
async def start_chat(db: Session = Depends(get_db)):
    id = str(uuid.uuid4())
    db_chat = Chat(id=id)
    db.add(db_chat)
    db_message = Message(
        chat_id=db_chat.id,
        role="system",
        content=(
            "You are a restaurant AI assistant. "
            "The user will ask questions in English, and you should respond in English. "
            "You have access to database functions to retrieve menu information. "
            "Rules:\n"
            "1. If a menu does not exist in the DB, respond with 'I'm sorry, but we don't have that menu item.'\n"
            "2. If the menu name is vague or misspelled, try to find the closest match.\n"
            "3. If asked about halal menus, use `get_all_menu_details` and list items with `is_halal = true`.\n"
            "4. If asked 'What menus do you have?' call `list_menus` and show the menu list.\n"
            "5. If specific menu info is needed, call `get_menu_info` and respond based on the returned data.\n"
            "6. Do not make up false information.\n"
            "7. Currently, only respond to queries about menu information.\n"
            "8. If allergy information is requested, use the DB's `allergies` field.\n"
            "9. If asked to speak in English, answer in English.\n"
            "10. When asked about the menu in English, pick up what you think is appropriate from the DB information, translate it into English, and reply.\n"
            "Always answer in a polite and helpful manner in English."
        )
    )
    db.add(db_message)
    db.commit()

    return {"chat_id": id}

functions = [
    {
        "name": "get_menu_info",
        "description": "メニュー名をもとにメニュー情報を取得する",
        "parameters": {
            "type": "object",
            "properties": {
                "menu_name": {"type": "string"}
            },
            "required": ["menu_name"]
        }
    },
    {
        "name": "list_menus",
        "description": "メニュー一覧を取得する",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_all_menu_details",
        "description": "全メニューの詳細情報を取得する",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

def call_openai(messages, db: Session):
    response = client.chat.completions.create(model="gpt-4-0613",
    messages=messages,
    functions=functions,
    function_call="auto")

    if response.choices[0].finish_reason == "function_call":
        fn_name = response.choices[0].message.function_call.name
        fn_args = json.loads(response.choices[0].message.function_call.arguments)

        if fn_name == "get_menu_info":
            menu_info = get_menu_info_from_db(fn_args["menu_name"], db)
            if menu_info is None:
                answer = "申し訳ありません、そのようなメニューはありません。"
                return answer
            else:
                follow_messages = messages + [{
                    "role": "function",
                    "name": fn_name,
                    "content": json.dumps(menu_info, ensure_ascii=False)
                }]
                follow_response = client.chat.completions.create(model="gpt-4-0613",
                messages=follow_messages)
                return follow_response.choices[0].message.content.strip()

        elif fn_name == "list_menus":
            menu_names = get_all_menus(db)
            follow_messages = messages + [{
                "role": "function",
                "name": fn_name,
                "content": json.dumps({"menus": menu_names}, ensure_ascii=False)
            }]
            follow_response = client.chat.completions.create(model="gpt-4-0613",
            messages=follow_messages)
            return follow_response.choices[0].message.content.strip()

        elif fn_name == "get_all_menu_details":
            all_details = get_all_menu_details(db)
            follow_messages = messages + [{
                "role": "function",
                "name": fn_name,
                "content": json.dumps(all_details, ensure_ascii=False)
            }]
            follow_response = client.chat.completions.create(model="gpt-4-0613",
            messages=follow_messages)
            return follow_response.choices[0].message.content.strip()

    else:
        return response.choices[0].message.content.strip()


@router.post("/chat/{chat_id}")
async def chat_endpoint(chat_id: str, message: ChatMessageInput, db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    db_user_message = Message(chat_id=chat_id, role="user", content=message.content)
    db.add(db_user_message)
    db.commit()

    chat_messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()
    messages = [{"role": m.role, "content": m.content} for m in chat_messages]

    response_text = call_openai(messages, db)
    return StreamingResponse(chat_stream(response_text, chat_id, db), media_type="text/event-stream")
