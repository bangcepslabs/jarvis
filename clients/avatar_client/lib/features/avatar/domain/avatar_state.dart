enum AvatarState { idle, listening, thinking, speaking, error }
extension AvatarStateLabel on AvatarState { String get label => switch (this) { AvatarState.idle => 'Idle', AvatarState.listening => 'Listening...', AvatarState.thinking => 'Thinking...', AvatarState.speaking => 'Speaking...', AvatarState.error => 'Connection error' }; }
