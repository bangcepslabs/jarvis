import 'package:flutter/material.dart';
import '../controller/avatar_controller.dart';
import '../domain/avatar_state.dart';
import 'avatar_renderer.dart';

class AvatarScreen extends StatefulWidget {
  const AvatarScreen({
    super.key,
    required this.controller,
    required this.rendererConfig,
  });
  final AvatarController controller;
  final AvatarRendererConfig rendererConfig;
  @override
  State<AvatarScreen> createState() => _AvatarScreenState();
}

class _AvatarScreenState extends State<AvatarScreen> with WidgetsBindingObserver {
  static const surfaceColor = Color(0xff151a22);
  final input = TextEditingController();
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    widget.controller.addListener(refresh);
  }

  void refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    widget.controller.removeListener(refresh);
    input.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    widget.controller.handleLifecycle(state);
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final state = controller.state;
    return Scaffold(
      backgroundColor: const Color(0xff07111d),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(
            child: ValueListenableBuilder<double>(
              valueListenable: controller.mouthOpen,
              builder: (context, mouthOpen, child) => AvatarRendererHost(
                config: widget.rendererConfig,
                state: state,
                size: double.infinity,
                presentationHint: controller.presentationHint,
                mouthOpen: mouthOpen,
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Text(
                        state.label,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.white70,
                        ),
                      ),
                      if (controller.wakeWordEnabled || controller.wakeWordStatus == 'unavailable')
                        Text(
                          controller.wakeWordStatus == 'unavailable'
                              ? 'Wake Word unavailable'
                              : 'Wake Word ON',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54),
                        ),
                    ],
                  ),
                  const Spacer(),
                  if (controller.reply.isNotEmpty ||
                      controller.errorMessage != null)
                    Align(
                      alignment: Alignment.center,
                      child: Container(
                        constraints: const BoxConstraints(maxWidth: 560),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 18,
                          vertical: 12,
                        ),
                        color: const Color(0xcc07111d),
                        child: Text(
                          controller.errorMessage ?? controller.reply,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: controller.errorMessage == null
                                ? Colors.white
                                : Colors.redAccent,
                          ),
                        ),
                      ),
                    ),
                  const SizedBox(height: 18),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(
                        child: TextField(
                          controller: input,
                          onSubmitted: (value) {
                            controller.sendText(value);
                            input.clear();
                          },
                          decoration: const InputDecoration(
                            hintText: 'Type to JARVIS...',
                            filled: true,
                            fillColor: surfaceColor,
                            border: OutlineInputBorder(
                              borderSide: BorderSide(color: Colors.white24),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderSide: BorderSide(color: Colors.white24),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderSide: BorderSide(color: Colors.lightBlueAccent),
                            ),
                            isDense: true,
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 12,
                            ),
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Send message',
                        onPressed: () {
                          controller.sendText(input.text);
                          input.clear();
                        },
                        icon: const Icon(Icons.send),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        FloatingActionButton(
                          tooltip: 'Toggle microphone',
                          onPressed: controller.toggleRecording,
                          backgroundColor: controller.isRecording
                              ? Colors.redAccent
                              : const Color(0xff1596bd),
                          child: Icon(controller.isRecording ? Icons.stop : Icons.mic),
                        ),
                        const SizedBox(width: 12),
                        Tooltip(
                          message: 'Enable local wake word detection',
                          child: Switch(
                            value: controller.wakeWordEnabled,
                            onChanged: controller.setWakeWordEnabled,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
