"""Clases generadas automaticamente usando ciertas herramientas de formateo
de json automatico.
"""

# Herramienta en cuestion: https://jsonformatter.org/json-to-python

from typing import List, Any
from datetime import datetime

class MessageReference:
    def __init__(self, **kwargs):
        self.message_id = kwargs.get('message_id')
        self.channel_id = kwargs.get('channel_id')
        self.guild_id = kwargs.get('guild_id')
        self.fail_if_not_exists = kwargs.get('fail_if_not_exists')


class Author:
    username: str
    public_flags: int
    id: str
    global_name: str
    discriminator: int
    avatar_decoration_data: None
    avatar: str
    bot: bool | None
    clan: Any | None

    def __init__(self, username: str, public_flags: int, id: str, global_name: str, discriminator: int, avatar_decoration_data: None, avatar: str, bot: bool | None = None, clan: Any | None = None) -> None:
        self.username = username
        self.public_flags = public_flags
        self.id = id
        self.global_name = global_name
        self.discriminator = discriminator
        self.avatar_decoration_data = avatar_decoration_data
        self.avatar = avatar
        self.bot = bot
        self.clan = clan


class Member:
    roles: List[Any]
    premium_since: None
    pending: bool
    nick: None
    mute: bool
    joined_at: datetime
    flags: int
    deaf: bool
    communication_disabled_until: None
    avatar: None

    def __init__(self, roles: List[Any], premium_since: None, pending: bool, nick: None, mute: bool, joined_at: datetime, flags: int, deaf: bool, communication_disabled_until: None, avatar: None) -> None:
        self.roles = roles
        self.premium_since = premium_since
        self.pending = pending
        self.nick = nick
        self.mute = mute
        self.joined_at = joined_at
        self.flags = flags
        self.deaf = deaf
        self.communication_disabled_until = communication_disabled_until
        self.avatar = avatar

class Message:

    # Documentacion oficial: https://discord.com/developers/docs/resources/channel#message-object
    type: int
    tts: bool
    timestamp: datetime
    referenced_message: None
    pinned: bool
    nonce: str | None
    mention_roles: List[Any]
    mention_everyone: bool
    id: str
    flags: int
    embeds: List[Any]
    edited_timestamp: None
    content: str
    components: List[Any]
    channel_id: str
    author: Any | Author
    attachments: List[Any]

    def __init__(self, type: int, tts: bool, timestamp: datetime, pinned: bool, mention_roles: List[Any], mention_everyone: bool, id: str, flags: int, embeds: List[Any], edited_timestamp: None, content: str, components: List[Any], channel_id: str, author: Any | Author, attachments: List[Any], nonce: str | None = None, message_reference: MessageReference | None = None, webhook_id: str | None = None, resolved = None, role_subscription_data = None, position = None, interaction_metadata = None, application_id = None, referenced_message: None = None) -> None:
        self.type = type
        self.tts = tts
        self.timestamp = timestamp
        self.referenced_message = referenced_message
        self.pinned = pinned
        self.nonce = nonce
        self.mention_roles = mention_roles
        self.mention_everyone = mention_everyone
        self.id = id
        self.flags = flags
        self.embeds = embeds
        self.edited_timestamp = edited_timestamp
        self.content = content
        self.components = components
        self.channel_id = channel_id
        self.author = author if isinstance(author, Author) else Author(**author)
        self.attachments = attachments
        self.message_reference = message_reference if isinstance(message_reference, MessageReference) else MessageReference(**message_reference) if message_reference else None
        self.webhook_id = webhook_id
        self.position = position
        self.role_subscription_data = role_subscription_data
        self.resolved = resolved
        self.interaction_metadata = interaction_metadata
        self.application_id = application_id


class CreateMessage(Message):
    """Objeto raiz del evento MESSAGE_CREATE del GatewayAPI.
    """
    guild_id: str
    member: Any | Member
    mentions: List[Any]

    def __init__(self, guild_id: str, member: Any | Member, mentions: List[Any], **kwargs):
        super().__init__(**kwargs)
        self.mentions = mentions
        self.member = member if isinstance(member, Member) else Member(**member)
        self.guild_id = guild_id


class Application:
    id: str
    flags: int

    def __init__(self, id: str, flags: int) -> None:
        self.id = id
        self.flags = flags


class Auth:
    pass

    def __init__(self, ) -> None:
        pass


class Guild:
    unavailable: bool
    id: str

    def __init__(self, unavailable: bool, id: str) -> None:
        self.unavailable = unavailable
        self.id = id


class User:
    verified: bool
    username: str
    mfa_enabled: bool
    id: str
    global_name: None
    flags: int
    email: None
    discriminator: int
    bot: bool
    avatar: None
    clan: Any | None

    def __init__(self, verified: bool, username: str, mfa_enabled: bool, id: str, global_name: None, flags: int, email: None, discriminator: int, bot: bool, avatar: None, clan: Any | None = None) -> None:
        self.verified = verified
        self.username = username
        self.mfa_enabled = mfa_enabled
        self.id = id
        self.global_name = global_name
        self.flags = flags
        self.email = email
        self.discriminator = discriminator
        self.bot = bot
        self.avatar = avatar
        self.clan = clan

class AuthorizedUser(User):
    """Clase customizada para guardar el token de acceso.

    Parameters
    ----------
    token: str
        Token de acceso. A veces lo he visto ser llamado Token de Cliente
        (CLIENT TOKEN)

    kwargs: dict[Any, Any]
        Argumentos del constructor de la clase User
    """

    def __init__(self, token: str, **kwargs):
        super().__init__(**kwargs)
        self.token = token

class ReadyEvent:
    """Raiz del evento READY en la API Gateway de Discord.
    """
    v: int
    user_settings: Auth
    user: User | Any
    session_type: str
    session_id: str
    resume_gateway_url: str
    relationships: List[Any]
    private_channels: List[Any]
    presences: List[Any]
    guilds: List[Guild]
    guild_join_requests: List[Any]
    geo_ordered_rtc_regions: List[str]
    auth: Auth
    application: Application
    _trace: List[str]

    def __init__(self, v: int, user_settings: Auth, user: User | Any, session_type: str, session_id: str, resume_gateway_url: str, relationships: List[Any], private_channels: List[Any], presences: List[Any], guilds: List[Guild], guild_join_requests: List[Any], geo_ordered_rtc_regions: List[str], auth: Auth, application: Application, _trace: List[str]) -> None:
        self.v = v
        self.user_settings = user_settings
        self.user = user if isinstance(user, User) else User(**user)
        self.session_type = session_type
        self.session_id = session_id
        self.resume_gateway_url = resume_gateway_url
        self.relationships = relationships
        self.private_channels = private_channels
        self.presences = presences
        self.guilds = guilds
        self.guild_join_requests = guild_join_requests
        self.geo_ordered_rtc_regions = geo_ordered_rtc_regions
        self.auth = auth
        self.application = application
        self._trace = _trace

