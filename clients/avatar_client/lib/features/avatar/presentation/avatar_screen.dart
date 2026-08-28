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

class _AvatarScreenState extends State<AvatarScreen> {
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
              padding: const EdgeInsets.fromLTRB(24, 14, 24, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'JARVIS',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      Text(
                        state.label,
                        style: Theme.of(context).textTheme.titleMedium,
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
                            fillColor: Color(0xcc07111d),
                            border: OutlineInputBorder(),
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
                  const SizedBox(height: 14),
                  Center(
                    child: FloatingActionButton.large(
                      tooltip: 'Toggle microphone',
                      onPressed: controller.toggleRecording,
                      backgroundColor: controller.isRecording
                          ? Colors.redAccent
                          : const Color(0xff1596bd),
                      child: Icon(
                        controller.isRecording ? Icons.stop : Icons.mic,
                      ),
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
