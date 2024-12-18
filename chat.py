from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
from openai import OpenAI
from db import  get_db, Chat, Message, Menu
from model import ChatMessageInput
from config import OPENAI_API_KEY
import re

router = APIRouter()

client = OpenAI(api_key=OPENAI_API_KEY)

# ユーザーメッセージを解析してメニュー問い合わせかどうかを判断する簡易関数
def is_reservation_question(user_input: str) -> bool:
    # 「予約」というキーワードがあれば予約関連とみなして対応不可
    return "予約" in user_input

def is_halal_question(user_input: str) -> bool:
    # 「ハラール」というキーワードがあればハラール対応メニュー検索
    return "ハラール" in user_input or "halal" in user_input.lower()

def extract_menu_name(user_input: str, db: Session) -> str:
    # 簡易実装: データベースにあるメニュー名がユーザー入力に含まれていればそれを返す
    menus = db.query(Menu).all()
    for m in menus:
        if m.name in user_input:
            return m.name
    return ""

def split_sentence(content: str):
    pattern = r'([。、!?！？])'

    # 文章を分割
    parts = re.split(pattern, content)

    # 分割された部分を統合して文を作成
    sentences = []
    current_sentence = ''
    for part in parts:
        current_sentence += part
        if re.match(pattern, part):
            sentences.append(current_sentence)
            current_sentence = ''

    # 最後の文が句読点で終わっていない場合も追加
    if current_sentence:
        sentences.append(current_sentence)

    return sentences

def stream_json_res(obj: any) -> str:
    return f"{json.dumps(obj, ensure_ascii=False)}\n"

# OpenAIへの問い合わせ（fallback用）
def ask_gpt(messages):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        max_tokens=200,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

@router.post("/start_chat")
async def start_chat(db: Session = Depends(get_db)):
    id = str(uuid.uuid4())
    db_chat = Chat(id=id)
    db.add(db_chat)
    db_message = Message(
        chat_id=db_chat.id,
        role="system",
        content="あなたは飲食店のユーザーからの質問に対応するAIです。丁寧な言葉遣いで対応してください。"
    )
    db.add(db_message)
    db.commit()

    return {"chat_id": id}

async def chat_stream(response_text: str, chat_id: str, db: Session):
    splited_content = split_sentence(response_text)
    full_content = response_text
    for sentence in splited_content:
        yield stream_json_res({'content': sentence})
    # DBにアシスタントメッセージとして保存
    db_message = Message(
        chat_id=chat_id, role="assistant", content=full_content)
    db.add(db_message)
    db.commit()
    yield stream_json_res({'status': 'finished'})

@router.post("/chat/{chat_id}")
async def chat_endpoint(chat_id: str, message: ChatMessageInput, db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=404, detail="Chat not found")
    
    # ユーザーメッセージをDBに保存
    db_message = Message(
        chat_id=chat_id, role="user", content=message.content)
    db.add(db_message)
    db.commit()

    user_input = message.content.strip()

    # 予約関連判定
    if is_reservation_question(user_input):
        response_text = "申し訳ありません。現在予約には対応しておりません。"
        return StreamingResponse(chat_stream(response_text, chat_id, db), media_type="text/event-stream")

    # ハラール対応メニュー質問判定
    if is_halal_question(user_input):
        halal_menus = db.query(Menu).filter(Menu.is_halal == True).all()
        if halal_menus:
            names = [m.name for m in halal_menus]
            response_text = "ハラール対応メニューは以下のとおりです。\n" + "\n".join(names)
        else:
            response_text = "ハラール対応メニューは現在提供しておりません。"
        return StreamingResponse(chat_stream(response_text, chat_id, db), media_type="text/event-stream")

    # 特定メニュー名が含まれるかチェック
    menu_name = extract_menu_name(user_input, db)
    if menu_name:
        # メニュー詳細返答
        menu = db.query(Menu).filter(Menu.name == menu_name).first()
        if menu:
            response_text = f"{menu_name}の情報です。\n材料: {menu.ingredients}\nアレルギー: {menu.allergies}\nハラール対応: {'はい' if menu.is_halal else 'いいえ'}"
            return StreamingResponse(chat_stream(response_text, chat_id, db), media_type="text/event-stream")

    # 上記以外の質問はOpenAIに投げてみる
    # 一旦既存メッセージを全て取得
    messages = []
    chat_messages = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()
    for m in chat_messages:
        messages.append({"role": m.role, "content": m.content})

    gpt_answer = ask_gpt(messages)
    # 「わからない」や「答えられない」などが返ってきたら答えられない旨を送信
    # 簡易的にgpt_answerを判定
    if "わから" in gpt_answer or "不明" in gpt_answer or "答えられ" in gpt_answer:
        response_text = "申し訳ありません。その質問にはお答えできません。"
    else:
        response_text = gpt_answer

    return StreamingResponse(chat_stream(response_text, chat_id, db), media_type="text/event-stream")
