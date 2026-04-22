from aiogram.fsm.state import State, StatesGroup


class ContentStates(StatesGroup):
    """States for content handling flow"""

    waiting_description = State()
    waiting_title = State()
    waiting_comments_confirmation = State()
    waiting_url = State()
    waiting_link_download_decision = State()
    waiting_post_process_action = State()
    waiting_topic_expansion_dialog = State()
    waiting_expansion_save_confirmation = State()
    waiting_media_transcribe_confirmation = State()
    waiting_media_delete_confirmation = State()
