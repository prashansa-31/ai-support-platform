# import uuid

# from app.db.base import Base
# from app.models.conversation import (
#     Conversation,
#     ConversationPriority,
#     ConversationStatus,
#     Message,
#     MessageRole,
# )
# from app.models.user import User, UserRole


# def test_user_model_defaults():
#     user = User(
#         email="support@example.com",
#         hashed_password="hashed_pw_secret",
#         full_name="Alex Support",
#     )
#     assert user.email == "support@example.com"
#     assert user.role == UserRole.CUSTOMER
#     assert user.is_active is True
#     # id has default callable
#     assert user.id is not None or user.__table__.c.id.default.arg() is not None


# def test_conversation_model_defaults():
#     user_id = str(uuid.uuid4())
#     conv = Conversation(
#         user_id=user_id,
#         title="Cannot reset password",
#     )
#     assert conv.user_id == user_id
#     assert conv.title == "Cannot reset password"
#     assert conv.status == ConversationStatus.ACTIVE
#     assert conv.priority == ConversationPriority.NORMAL


# def test_message_model_structure():
#     conv_id = str(uuid.uuid4())
#     msg = Message(
#         conversation_id=conv_id,
#         role=MessageRole.USER,
#         content="I need help with my account.",
#         sequence_number=1,
#         token_count=12,
#         metadata_json={"ip": "127.0.0.1"},
#     )
#     assert msg.conversation_id == conv_id
#     assert msg.role == MessageRole.USER
#     assert msg.content == "I need help with my account."
#     assert msg.sequence_number == 1
#     assert msg.token_count == 12
#     assert msg.metadata_json == {"ip": "127.0.0.1"}


# def test_table_metadata_and_constraints():
#     # Verify all expected tables exist in SQLAlchemy metadata
#     table_names = Base.metadata.tables.keys()
#     assert "users" in table_names
#     assert "conversations" in table_names
#     assert "messages" in table_names

#     # Verify messages unique constraint on (conversation_id, sequence_number)
#     messages_table = Base.metadata.tables["messages"]
#     unique_constraints = [
#         c.name for c in messages_table.constraints if hasattr(c, "columns")
#     ]
#     assert "uq_conversation_sequence" in unique_constraints

#     # Verify foreign key cascade on conversation -> messages
#     fk_targets = [
#         fk.target_fullname
#         for col in messages_table.columns
#         for fk in col.foreign_keys
#     ]
#     assert "conversations.id" in fk_targets
