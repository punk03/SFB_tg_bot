from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

vk_token = os.getenv('VK_TOKEN')
vk_group_id = os.getenv('VK_GROUP_ID')

tg_bot_token = os.getenv('TG_BOT_TOKEN')
tg_group_id = os.getenv('TG_GROUP_ID')

api_id = 19890531
api_hash = '7ec8158285a1d583eaea1d881c70ca2e'



hashtags = ['#работамастера_сфб',
            '#мастера_сфб',
            '#объявления_сфб',
            '#информация_сфб',
            '#вопросы_сфб',
            '#интересное_сфб',
            '#лайфхаки_сфб',
            '#юмор_сфб',
            '#магазиныпартнеры_сфб',
            '#акциямагазинапартнера_сфб',
            '#вопросымастера_сфб',
            '#объявления_сфб',
            '#отзывы_сфб',
            '#зож_сфб',
            ]

"""topics = {
          '#вопросымастера_сфб': '28'}"""
topics = {'#работамастера_сфб': '3',
            '#мастера_сфб': '5',
            '#объявления_сфб': '30',
            '#информация_сфб': '12',
            '#вопросы_сфб': '16',
            '#интересное_сфб': '18',
            '#лайфхаки_сфб': '20',
            '#юмор_сфб': '22',
            '#магазиныпартнеры_сфб': '24',
            '#акциямагазинапартнера_сфб': '26',
            '#вопросымастера_сфб': '28',
            '#объявления_сфб': '30',
            '#отзывы_сфб': '32',
            '#зож_сфб': '14'}



