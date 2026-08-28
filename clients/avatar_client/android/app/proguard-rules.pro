# Live2D CubismCoreJNI looks up framework classes while loading its native
# library. Preserve the SDK package if release shrinking is enabled later.
-keep class com.live2d.sdk.cubism.** { *; }
-keep class com.example.avatar_client.** { *; }
