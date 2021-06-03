# author: Arwichok
# telegram: t.me/arwichok

import logging

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import Message, LabeledPrice
from aiogram.utils.callback_data import CallbackData
from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env("BOT_TOKEN")
PAY_TOKEN = env("PAY_TOKEN")


# WARNING: USED ONLY FOR TEST, IN PROD USE REAL DB
DB = {
    # "{user_id}": {"b": {"1": 2}}
}

bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)


product_cd = CallbackData("p", "pid")
to_bucket_cd = CallbackData("tb", "pid")
remove_bucket_cd = CallbackData("rb", "pid")

products = {
    "0": "Яблука",
    "1": "Апельсины",
}


def product_button(name: str, pid):
    return types.InlineKeyboardButton(name, callback_data=product_cd.new(pid))


def bucket_product_row(pid, count):
    return [
        types.InlineKeyboardButton(f"{products.get(pid)} [{count}]", callback_data="_"),
        types.InlineKeyboardButton("❌", callback_data=remove_bucket_cd.new(pid))
    ]


def welcome_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Каталог", callback_data="c"))
    markup.add(types.InlineKeyboardButton("Корзина", callback_data="b"))
    return dict(text="Добро пожаловать", reply_markup=markup)


def catalog():
    kb = [[product_button(name, pid)] for pid, name in products.items()]
    kb.append([types.InlineKeyboardButton("<< Назад", callback_data="w")])
    return dict(text="Каталог", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


def product(pid):
    return dict(text=products.get(pid), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton("В корзину 🛒", callback_data=to_bucket_cd.new(pid))],
        [types.InlineKeyboardButton("<< Назад", callback_data="c")]
    ]))


def bucket(suid):
    kb = [bucket_product_row(pid, count) for pid, count in DB[suid]["b"].items()] if DB.get(suid) else []
    if DB.get(suid):
        kb.append([types.InlineKeyboardButton("Заказать", callback_data="o")])
    kb.append([types.InlineKeyboardButton("<< Назад", callback_data="w")])
    return dict(text="Корзина", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


def order_markup():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton("Заплатить", pay=True)],
        [types.InlineKeyboardButton("<< Назад", callback_data="nb")]
    ])


@dp.message_handler(CommandStart())
async def start_cmd(msg: types.Message):
    await msg.answer(**welcome_markup())


@dp.callback_query_handler(product_cd.filter())
async def show_product(cq: types.CallbackQuery, callback_data):
    pid = callback_data.get("pid")
    await cq.message.edit_text(**product(pid))


@dp.callback_query_handler(to_bucket_cd.filter())
async def to_bucket(cq: types.CallbackQuery, callback_data):
    pid = callback_data.get("pid")
    suid = str(cq.from_user.id)
    name = products[pid][1]
    if not DB.get(suid):
        DB[suid] = {"b": {}}
    if DB[suid]["b"].get(pid):
        DB[suid]["b"][pid] += 1
    else:
        DB[suid]["b"][pid] = 1
    await cq.answer(f"{name} {pid} добавлено в корзину")


@dp.callback_query_handler(remove_bucket_cd.filter())
async def remove_from_bucket(cq: types.CallbackQuery, callback_data):
    suid = str(cq.from_user.id)
    pid = callback_data.get("pid")
    if DB.get(suid) and DB[suid]["b"].get(pid):
        DB[suid]["b"].pop(pid)
        await cq.message.edit_text(**bucket(suid))


@dp.callback_query_handler()
async def echo_cb(cq: types.CallbackQuery):
    suid = str(cq.from_user.id)
    if cq.data == "c":
        await cq.message.edit_text(**catalog())
    elif cq.data == "w":
        await cq.message.edit_text(**welcome_markup())
    elif cq.data == "b":
        if suid in DB and DB.get(suid)["b"]:
            await cq.message.edit_text(**bucket(suid))
        else:
            await cq.answer("Корзина пуста", show_alert=True)
            return
    elif cq.data == "o":
        prices = [LabeledPrice(label=f"{products[pid]} x{count}", amount=count*100)
                  for pid, count in DB[suid]["b"].items() if DB.get(suid)]
        if len(prices) >= 2:
            prices.append(LabeledPrice(label="скидка", amount=-100))
        await cq.message.delete()
        await cq.bot.send_invoice(
            chat_id=cq.from_user.id,
            title="Заказ продуктов",
            description="Описание...",
            payload="Payload",
            provider_token=PAY_TOKEN,
            currency="usd",
            prices=prices,
            reply_markup=order_markup(),
            photo_url="https://telegra.ph/file/36c56b25b4f733aed8435.png",
            photo_width=827,
            photo_height=555,
            max_tip_amount=1000,
            suggested_tip_amounts=[100, 200, 500, 1000],
            need_phone_number=True,
            need_email=True,
            need_name=True,
            need_shipping_address=True,
            is_flexible=True,
        )
    elif cq.data == "nb":
        await cq.message.delete()
        await cq.message.answer(**bucket(suid))

    await cq.answer()


@dp.pre_checkout_query_handler()
async def checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(
        query.id, ok=True, error_message="Error pre checkout"
    )


@dp.shipping_query_handler()
async def shipping(query: types.ShippingQuery):
    shipping_options = [
        types.ShippingOption(id="s1", title="Корабль").add(types.LabeledPrice("Доставка кораблём", 100)),
        types.ShippingOption(id="s2", title="Поезд").add(types.LabeledPrice("Доставка поездом", 200)),
    ]
    await query.bot.answer_shipping_query(
        query.id, ok=True, shipping_options=shipping_options, error_message="Error shipping")


@dp.message_handler(content_types=types.ContentTypes.SUCCESSFUL_PAYMENT)
async def got_pay(msg: Message):
    logging.info(f"{msg.successful_payment.order_info}")
    await msg.answer(f"Спасибо за оплату {msg.successful_payment.total_amount} {msg.successful_payment.currency:.2}")


if __name__ == '__main__':
    executor.start_polling(dp)
