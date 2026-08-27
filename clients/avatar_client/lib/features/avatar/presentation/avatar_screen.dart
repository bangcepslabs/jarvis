import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
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

class _AvatarScreenState extends State<AvatarScreen> {
  static const surfaceColor = Color(0xff151a22);
  static const backgroundColor = Color(0xff07111d);
  final input = TextEditingController();
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(refresh);
  }

  void refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.controller.removeListener(refresh);
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final state = controller.state;
    return Scaffold(
      backgroundColor: backgroundColor,
      body: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(
            child: AvatarRendererHost(
              config: widget.rendererConfig,
              state: state,
              size: double.infinity,
              mouthOpen: controller.mouthOpen,
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'JARVIS',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.4,
                        ),
                      ),
                      Text(
                        state.label,
                        style: Theme.of(
                          context,
                        ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
                      ),
                    ],
                  ),
                  if (kDebugMode &&
                      widget.rendererConfig.debugControls &&
                      widget.rendererConfig.kind == AvatarRendererKind.live2d)
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      children: [
                        for (final name in const [
                          'black',
                          'red',
                          'shock',
                          'shou',
                          'tang',
                          'shuiyin',
                        ])
                          TextButton(
                            onPressed: () => const MethodChannel(
                              'jarvis/live2d',
                            ).invokeMethod<void>('applyExpression', name),
                            child: Text(name),
                          ),
                        TextButton(
                          onPressed: () => const MethodChannel(
                            'jarvis/live2d',
                          ).invokeMethod<void>('clearExpression', ''),
                          child: const Text('clear'),
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
                              borderSide: BorderSide(
                                color: Colors.lightBlueAccent,
                              ),
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
                  if (controller.continuousSessionActive)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.only(bottom: 6),
                        child: Text(
                          'Continuous: ON',
                          style: TextStyle(
                            color: Colors.lightBlueAccent,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                  Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        FloatingActionButton(
                          tooltip: controller.continuousSessionActive
                              ? 'Stop continuous conversation'
                              : 'Toggle microphone',
                          onPressed: controller.toggleRecording,
                          backgroundColor: controller.isRecording
                              ? Colors.redAccent
                              : const Color(0xff1596bd),
                          child: Icon(
                            controller.isRecording ? Icons.stop : Icons.mic,
                          ),
                        ),
                        const SizedBox(width: 12),
                        IconButton.filled(
                          tooltip: 'Start continuous conversation',
                          onPressed: controller.continuousSessionActive
                              ? controller.cancelContinuousConversation
                              : controller.startContinuousConversation,
                          icon: Icon(
                            controller.continuousSessionActive
                                ? Icons.stop_circle
                                : Icons.forum,
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
