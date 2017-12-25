import config
import telebot
from telebot import types
import database
import requests
import numpy as np
import cv2

bot = telebot.TeleBot(config.bot_token)
user_cache = {}


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Hi and welcome to JukeboxJamsBot! This bot is here to help you find a perfect playlist to fit your mood. \n"
                                      "In order to find out what it can do, please enter the /help command")


@bot.message_handler(commands=['help'])
def help(message):
    bot.send_message(message.chat.id, "Here's what this bot can understand and do: \n"
                                      "/keyword - find a playlist by keyword that describes your mood \n"
                                      "/picture - find a playlist by image \n"
                                      "/favorites - show your liked playlists")


def print_result(list_of_results):
    res = '<b>' + list_of_results[1] + '</b>' + '\n'
    res += '<a href= "https://open.spotify.com/user/' + list_of_results[4] + '/playlist/' + list_of_results[0] + '">Spotify</a> \n'
    for i in range(len(list_of_results[2])):
        res += str(i + 1) + '. ' + list_of_results[2][i] + '\n'
    return res


@bot.message_handler(commands=['favorites'])
def favorites(message):
    all_results = database.getfavorites(message.chat.id)
    if (len(all_results)==0):
        bot.send_message(message.chat.id, "Nothing here yet, better start exploring!")
    else:
        res = print_result(all_results[0])
        user_query = {'last_msg': '', 'last_res': list(zip(all_results, [1 for i in all_results]))}
        user_cache[message.chat.id] = user_query.copy()
        msg = bot.send_message(message.chat.id, res, parse_mode='HTML', reply_markup=pages_keyboard(0, message.chat.id, 1))
        user_cache[message.chat.id]['last_msg'] = msg.message_id


@bot.message_handler(commands=['picture'])
def picture(message):
    msg = bot.send_message(message.chat.id, "Choose a picture that describes how you're feeling")
    bot.register_next_step_handler(msg, wait_for_picture)

def wait_for_picture(message):
    if message.photo is None:
        bot.send_message(message.chat.id, "Hmmm... pretty sure that's not a picture")
    else:
        file_info = bot.get_file(message.photo[0].file_id)
        url = "https://api.telegram.org/file/bot" + config.bot_token + "/" + file_info.file_path
        bot.send_chat_action(message.chat.id, 'typing')
        image = np.asarray(bytearray(requests.get(url).content), dtype="uint8")
        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([image], [0, 1], None, [200, 128],
                            [0, 360, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        results = {}
        for row in database.get_color_histograms():
            row_hist = np.asarray(row[1], dtype=np.float32)
            distance = cv2.compareHist(hist, row_hist, cv2.HISTCMP_BHATTACHARYYA)
            results[row[0]] = distance
        results = sorted([(v, k) for (k, v) in results.items()])
        results = database.get_playlist(results[0][1])
        res = print_result(results)
        bot.send_photo(message.chat.id, requests.get(results[5]).content)
        bot.send_message(message.chat.id, res, parse_mode='HTML')


@bot.message_handler(commands=['keyword'])
def keyword(message):
    msg = bot.send_message(message.chat.id, "Choose the best word to describe your mood")
    bot.register_next_step_handler(msg, wait_for_keyword)


def wait_for_keyword(message):
    global user_cache
    key = message.text
    all_results = database.getbykeyword(key)
    if (len(all_results) != 0):
        res = print_result(all_results[0][0])
        user_query = {'last_msg': '', 'last_res': all_results}
        user_cache[message.chat.id] = user_query.copy()
        msg = bot.send_message(message.chat.id, res, parse_mode='HTML',
                               reply_markup=pages_keyboard(0, message.chat.id, 0))
        user_cache[message.chat.id]['last_msg'] = msg.message_id
    else:
        bot.send_message(message.chat.id, "Sorry, the bot couldn't find anything! Try again?")


def pages_keyboard(number, user_id, mode):
    keyboard = types.InlineKeyboardMarkup(4)
    btns = []
    if (mode == 1):
        btns.append(types.InlineKeyboardButton(
            text='💔', callback_data='dislike_' + str(number)))
    else:
        btns.append(types.InlineKeyboardButton(
            text='❤', callback_data='like_' + str(number)))
    btns.append(types.InlineKeyboardButton(
        text='🎨', callback_data='show_cover_' + str(number)))
    if number > 0: btns.append(types.InlineKeyboardButton(
        text='⬅', callback_data=str(mode)+'to_{}'.format(number-1)))
    if number < len(user_cache[user_id]['last_res']) - 1: btns.append(types.InlineKeyboardButton(
        text='➡', callback_data=str(mode)+'to_{}'.format(number+1)))
    keyboard.add(*btns)
    return keyboard


@bot.callback_query_handler(func=lambda c: c.data)
def pages(c):
    try:
        if user_cache[c.message.chat.id]['last_msg'] != c.message.message_id:
            return
    except KeyError:
        return
    if 'to_' in c.data:
        res = print_result(user_cache[c.message.chat.id]['last_res'][int(c.data[4:])][0])
        bot.edit_message_text(
            chat_id=c.message.chat.id,
            message_id=c.message.message_id,
            text=res,
            parse_mode='HTML',
            reply_markup=pages_keyboard(int(c.data[4:]), c.message.chat.id, int(c.data[0])))
    elif 'dislike_' in c.data:
        res_msg = database.removefromfavorite(user_cache[c.message.chat.id]['last_res'][int(c.data[8:])][0][0], c.message.chat.id)
        bot.answer_callback_query(c.id, show_alert=True, text=res_msg)
        all_results = database.getfavorites(c.message.chat.id)
        if (len(all_results) == 0):
            bot.edit_message_text(
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                text="Nothing here yet, better start exploring!",
                parse_mode='HTML')
        else:
            res = print_result(all_results[0][0])
            bot.edit_message_text(
                chat_id=c.message.chat.id,
                message_id=c.message.message_id,
                text=res,
                parse_mode='HTML',
                reply_markup=pages_keyboard(int(c.data[4:]), c.message.chat.id, 1))
    elif 'like_' in c.data:
        res = database.addtofavorite(user_cache[c.message.chat.id]['last_res'][int(c.data[5:])][0][0], c.message.chat.id)
        bot.answer_callback_query(c.id, show_alert=True, text=res)
    elif 'show_cover_' in c.data:
        img = database.get_playlist_image(user_cache[c.message.chat.id]['last_res'][int(c.data[11:])][0][0], user_cache[c.message.chat.id]['last_res'][int(c.data[11:])][0][4])
        bot.send_photo(c.message.chat.id, requests.get(img).content)


if __name__ == '__main__':
     bot.polling(none_stop=True)