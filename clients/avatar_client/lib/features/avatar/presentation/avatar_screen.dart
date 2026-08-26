import 'package:flutter/material.dart';
import '../controller/avatar_controller.dart';
import '../domain/avatar_state.dart';

class AvatarScreen extends StatefulWidget {
  const AvatarScreen({super.key, required this.controller});
  final AvatarController controller;
  @override State<AvatarScreen> createState() => _AvatarScreenState();
}

class _AvatarScreenState extends State<AvatarScreen> {
  final input = TextEditingController();
  @override void initState() { super.initState(); widget.controller.addListener(refresh); }
  void refresh() { if (mounted) setState(() {}); }
  @override void dispose() { widget.controller.removeListener(refresh); input.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final state = controller.state;
    return Scaffold(
      backgroundColor: const Color(0xff07111d),
      appBar: AppBar(title: const Text('JARVIS'), backgroundColor: Colors.transparent, actions: [Padding(padding: const EdgeInsets.all(16), child: Text(state.label))]),
      body: SafeArea(child: LayoutBuilder(builder: (context, constraints) {
        final size = constraints.maxWidth < 600 ? constraints.maxWidth * .62 : 360.0;
        return Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(children: [
            _Avatar(state, size),
            const SizedBox(height: 20),
            Text(state.label, style: Theme.of(context).textTheme.titleLarge),
            if (controller.errorMessage != null) Text(controller.errorMessage!, style: const TextStyle(color: Colors.redAccent)),
            if (controller.reply.isNotEmpty) Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(controller.reply))),
            const SizedBox(height: 18),
            Row(children: [
              Expanded(child: TextField(controller: input, onSubmitted: (value) { controller.sendText(value); input.clear(); }, decoration: const InputDecoration(hintText: 'Type to JARVIS...', border: OutlineInputBorder()))),
              IconButton(onPressed: () { controller.sendText(input.text); input.clear(); }, icon: const Icon(Icons.send)),
            ]),
            const SizedBox(height: 18),
            FloatingActionButton.large(onPressed: controller.toggleRecording, backgroundColor: controller.isRecording ? Colors.redAccent : const Color(0xff1596bd), child: Icon(controller.isRecording ? Icons.stop : Icons.mic)),
          ]),
        )));
      })),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar(this.state, this.size);
  final AvatarState state;
  final double size;
  @override
  Widget build(BuildContext context) => AnimatedContainer(
    duration: const Duration(milliseconds: 300), width: size, height: size,
    decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xff102b43), border: Border.all(color: state == AvatarState.error ? Colors.redAccent : const Color(0xff62d8ff), width: 3), boxShadow: [BoxShadow(color: const Color(0xff1596bd).withValues(alpha: .25), blurRadius: state == AvatarState.thinking ? 36 : 18)]),
    child: Center(child: Icon(switch (state) { AvatarState.idle => Icons.face_6, AvatarState.listening => Icons.hearing, AvatarState.thinking => Icons.psychology, AvatarState.speaking => Icons.record_voice_over, AvatarState.error => Icons.error_outline }, size: size * .3, color: const Color(0xffb8efff))),
  );
}
