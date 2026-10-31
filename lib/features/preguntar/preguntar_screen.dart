import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../core/providers/app_provider.dart';
import '../../core/services/backend_service.dart';
import '../../data/models/respuesta_pregunta.dart';

const _kPrimario = Color(0xFF012D1D);
const _kPrimarioSuave = Color(0xFFC1ECD4);
const _kFondo = Color(0xFFFCF9F4);
const _kTierra = Color(0xFF8B5E3C);
const _kBorde = Color(0xFFE5E2DD);

/// El campesino pregunta con su voz (o escribiendo) y Gemma 4 contesta con los datos de su municipio.
/// La respuesta se lee en voz alta y muestra las palabras en zapoteco del glosario.
class PreguntarScreen extends StatefulWidget {
  const PreguntarScreen({super.key});

  @override
  State<PreguntarScreen> createState() => _PreguntarScreenState();
}

class _PreguntarScreenState extends State<PreguntarScreen> {
  final _stt = SpeechToText();
  final _tts = FlutterTts();
  final _controlTexto = TextEditingController();

  bool _vozDisponible = false;
  bool _escuchando = false;
  bool _enviando = false;
  bool _hablando = false;
  String? _localeVoz;
  String _parcial = '';
  String? _error;
  RespuestaPregunta? _respuesta;

  static const _ejemplos = [
    '¿Qué puedo sembrar este mes?',
    '¿Cuándo siembro frijol?',
    '¿Cuánto llueve en esta época?',
    '¿Bata siembro dháh?',
  ];

  @override
  void initState() {
    super.initState();
    _prepararVoz();
    _prepararLectura();
  }

  Future<void> _prepararVoz() async {
    try {
      final ok = await _stt.initialize(
        onStatus: (estado) {
          if (!mounted) return;
          if (estado == 'done' || estado == 'notListening') {
            setState(() => _escuchando = false);
          }
        },
        onError: (e) {
          if (!mounted) return;
          setState(() {
            _escuchando = false;
            _error = e.errorMsg == 'error_no_match'
                ? 'No te escuché bien. Intenta otra vez, más cerca del teléfono.'
                : 'No se pudo usar el micrófono (${e.errorMsg}).';
          });
        },
      );
      String? locale;
      if (ok) {
        final locales = await _stt.locales();
        final ids = locales.map((l) => l.localeId).toList();
        // Español de México primero; si no, cualquier español
        locale = ids.firstWhere(
          (id) => id.startsWith('es_MX') || id.startsWith('es-MX'),
          orElse: () => ids.firstWhere((id) => id.startsWith('es'), orElse: () => ''),
        );
      }
      if (!mounted) return;
      setState(() {
        _vozDisponible = ok;
        _localeVoz = (locale == null || locale.isEmpty) ? null : locale;
      });
    } catch (e) {
      debugPrint('[Voz] no disponible: $e');
    }
  }

  Future<void> _prepararLectura() async {
    try {
      await _tts.setLanguage('es-MX');
      await _tts.setSpeechRate(0.45); // más despacio que el valor por defecto
      _tts.setStartHandler(() => _marcarHablando(true));
      _tts.setCompletionHandler(() => _marcarHablando(false));
      _tts.setCancelHandler(() => _marcarHablando(false));
      _tts.setErrorHandler((_) => _marcarHablando(false));
    } catch (e) {
      debugPrint('[Voz] lectura no disponible: $e');
    }
  }

  void _marcarHablando(bool valor) {
    if (mounted) setState(() => _hablando = valor);
  }

  @override
  void dispose() {
    _stt.cancel();
    _tts.stop();
    _controlTexto.dispose();
    super.dispose();
  }

  Future<void> _alternarEscucha() async {
    if (_escuchando) {
      await _stt.stop();
      setState(() => _escuchando = false);
      return;
    }
    await _tts.stop();
    setState(() {
      _error = null;
      _parcial = '';
      _escuchando = true;
    });
    await _stt.listen(
      onResult: _alEscuchar,
      listenOptions: SpeechListenOptions(
        localeId: _localeVoz,
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
        partialResults: true,
        listenMode: ListenMode.confirmation,
        cancelOnError: true,
      ),
    );
  }

  void _alEscuchar(SpeechRecognitionResult r) {
    setState(() => _parcial = r.recognizedWords);
    if (r.finalResult && r.recognizedWords.trim().isNotEmpty) {
      _enviar(r.recognizedWords);
    }
  }

  Future<void> _enviar(String texto) async {
    final pregunta = texto.trim();
    if (pregunta.isEmpty || _enviando) return;
    FocusScope.of(context).unfocus();
    final municipio = context.read<AppProvider>().municipioSeleccionado;

    setState(() {
      _enviando = true;
      _escuchando = false;
      _error = null;
      _parcial = pregunta;
    });
    try {
      final r = await BackendService.preguntar(texto: pregunta, municipio: municipio);
      if (!mounted) return;
      setState(() {
        _respuesta = r;
        _controlTexto.clear();
      });
      await _leer(r);
    } catch (e) {
      debugPrint('[Preguntar] $e');
      if (!mounted) return;
      setState(() => _error = 'No pudimos conectar con Lu-nisa. Revisa la conexión con el servidor en Perfil.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _leer(RespuestaPregunta r) async {
    await _tts.stop();
    await _tts.speak(r.respuesta);
  }

  @override
  Widget build(BuildContext context) {
    final municipio = context.watch<AppProvider>().municipioSeleccionado;

    return Scaffold(
      backgroundColor: _kFondo,
      appBar: AppBar(
        backgroundColor: const Color(0xFFF5F3EF),
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: _kPrimario),
          onPressed: () => context.canPop() ? context.pop() : context.go('/inicio'),
        ),
        title: const Text(
          'Pregúntale a Lu-nisa',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: _kPrimario),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          children: [
            _Municipio(municipio: municipio),
            const SizedBox(height: 24),
            _BotonMicrofono(
              escuchando: _escuchando,
              enviando: _enviando,
              disponible: _vozDisponible,
              onTap: _alternarEscucha,
            ),
            const SizedBox(height: 12),
            Text(
              _enviando
                  ? 'Pensando…'
                  : _escuchando
                      ? 'Te escucho…'
                      : _vozDisponible
                          ? 'Toca el micrófono y pregunta'
                          : 'Escribe tu pregunta abajo',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 16, color: _kPrimario, fontWeight: FontWeight.w600),
            ),
            if (_parcial.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                '“$_parcial”',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, fontStyle: FontStyle.italic, color: Color(0xFF555555)),
              ),
            ],
            if (_respuesta?.preguntaTraducida != null && !_enviando) ...[
              const SizedBox(height: 4),
              Text(
                'Entendimos: ${_respuesta!.preguntaTraducida}',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 14, color: _kTierra, fontWeight: FontWeight.w600),
              ),
            ],
            const SizedBox(height: 20),
            _CampoTexto(
              controlador: _controlTexto,
              habilitado: !_enviando,
              onEnviar: () => _enviar(_controlTexto.text),
            ),
            if (_respuesta == null && !_enviando) ...[
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final e in _ejemplos)
                    ActionChip(
                      label: Text(e),
                      backgroundColor: Colors.white,
                      side: const BorderSide(color: _kBorde),
                      onPressed: () => _enviar(e),
                    ),
                ],
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 16),
              _Aviso(texto: _error!),
            ],
            if (_respuesta != null) ...[
              const SizedBox(height: 24),
              _TarjetaRespuesta(
                respuesta: _respuesta!,
                hablando: _hablando,
                onEscuchar: () => _hablando ? _tts.stop() : _leer(_respuesta!),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Municipio extends StatelessWidget {
  final String? municipio;
  const _Municipio({required this.municipio});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.place_outlined, color: _kTierra, size: 20),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            municipio ?? 'Sin municipio: las respuestas serán generales',
            style: const TextStyle(fontSize: 14, color: Color(0xFF555555)),
          ),
        ),
        if (municipio == null)
          TextButton(
            onPressed: () => context.go('/municipio?from=inicio'),
            child: const Text('Elegir'),
          ),
      ],
    );
  }
}

class _BotonMicrofono extends StatelessWidget {
  final bool escuchando;
  final bool enviando;
  final bool disponible;
  final VoidCallback onTap;

  const _BotonMicrofono({
    required this.escuchando,
    required this.enviando,
    required this.disponible,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final activo = disponible && !enviando;
    return Center(
      child: Semantics(
        button: true,
        label: escuchando ? 'Dejar de escuchar' : 'Preguntar con la voz',
        child: GestureDetector(
          onTap: activo ? onTap : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: escuchando ? 128 : 112,
            height: escuchando ? 128 : 112,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: !activo ? const Color(0xFFBDBDBD) : (escuchando ? _kTierra : _kPrimario),
              boxShadow: [
                if (escuchando)
                  BoxShadow(color: _kTierra.withValues(alpha: 0.35), blurRadius: 24, spreadRadius: 6),
              ],
            ),
            child: enviando
                ? const Padding(
                    padding: EdgeInsets.all(40),
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                  )
                : Icon(
                    escuchando ? Icons.stop_rounded : Icons.mic_rounded,
                    color: Colors.white,
                    size: 52,
                  ),
          ),
        ),
      ),
    );
  }
}

class _CampoTexto extends StatelessWidget {
  final TextEditingController controlador;
  final bool habilitado;
  final VoidCallback onEnviar;

  const _CampoTexto({required this.controlador, required this.habilitado, required this.onEnviar});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controlador,
      enabled: habilitado,
      textInputAction: TextInputAction.send,
      onSubmitted: (_) => onEnviar(),
      decoration: InputDecoration(
        hintText: 'O escribe tu pregunta…',
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _kBorde)),
        enabledBorder:
            OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: _kBorde)),
        suffixIcon: IconButton(
          icon: const Icon(Icons.send_rounded, color: _kPrimario),
          onPressed: habilitado ? onEnviar : null,
        ),
      ),
    );
  }
}

class _Aviso extends StatelessWidget {
  final String texto;
  const _Aviso({required this.texto});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3E0),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFFCC80)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: _kTierra),
          const SizedBox(width: 8),
          Expanded(child: Text(texto, style: const TextStyle(fontSize: 14))),
        ],
      ),
    );
  }
}

class _TarjetaRespuesta extends StatefulWidget {
  final RespuestaPregunta respuesta;
  final bool hablando;
  final VoidCallback onEscuchar;

  const _TarjetaRespuesta({required this.respuesta, required this.hablando, required this.onEscuchar});

  @override
  State<_TarjetaRespuesta> createState() => _TarjetaRespuestaState();
}

class _TarjetaRespuestaState extends State<_TarjetaRespuesta> {
  /// Mostrar las palabras en zapoteco dentro de la frase
  bool _conZapoteco = true;

  /// Traducción completa experimental (Gemma 4), se pide solo si el usuario toca el botón
  TraduccionExperimental? _traduccion;
  bool _traduciendo = false;
  String? _errorTraduccion;

  @override
  void didUpdateWidget(covariant _TarjetaRespuesta anterior) {
    super.didUpdateWidget(anterior);
    // Nueva pregunta: la traducción anterior ya no aplica
    if (anterior.respuesta != widget.respuesta) {
      _traduccion = null;
      _errorTraduccion = null;
    }
  }

  Future<void> _traducir() async {
    setState(() {
      _traduciendo = true;
      _errorTraduccion = null;
    });
    try {
      final t = await BackendService.traducirZapoteco(widget.respuesta.respuesta);
      if (mounted) setState(() => _traduccion = t);
    } catch (e) {
      debugPrint('[Traducir] $e');
      if (mounted) setState(() => _errorTraduccion = 'No se pudo traducir ahora.');
    } finally {
      if (mounted) setState(() => _traduciendo = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final respuesta = widget.respuesta;
    final hablando = widget.hablando;
    final onEscuchar = widget.onEscuchar;
    final mezclar = _conZapoteco && respuesta.tieneZapotecoEnFrase;
    // Palabras de la pregunta y de la respuesta, sin repetir
    final palabras = <String, PalabraZapoteca>{
      for (final p in [...respuesta.zapotecoPregunta, ...respuesta.zapoteco]) p.espanol: p,
    }.values.toList();

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _kBorde, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '${respuesta.saludo}!',
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: _kPrimario),
              ),
              const Spacer(),
              IconButton.filledTonal(
                tooltip: hablando ? 'Detener' : 'Escuchar respuesta',
                onPressed: onEscuchar,
                icon: Icon(hablando ? Icons.stop_rounded : Icons.volume_up_rounded),
              ),
            ],
          ),
          const SizedBox(height: 8),
          mezclar
              ? _FraseConZapoteco(segmentos: respuesta.segmentos)
              : Text(respuesta.respuesta, style: const TextStyle(fontSize: 17, height: 1.45)),
          if (respuesta.tieneZapotecoEnFrase)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                style: TextButton.styleFrom(padding: EdgeInsets.zero, foregroundColor: _kTierra),
                onPressed: () => setState(() => _conZapoteco = !_conZapoteco),
                icon: const Icon(Icons.translate_rounded, size: 18),
                label: Text(_conZapoteco ? 'Ver solo en español' : 'Ver con palabras en zapoteco'),
              ),
            ),
          const SizedBox(height: 8),
          if (_traduccion == null)
            OutlinedButton.icon(
              onPressed: _traduciendo ? null : _traducir,
              style: OutlinedButton.styleFrom(
                foregroundColor: _kTierra,
                side: const BorderSide(color: _kTierra),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              icon: _traduciendo
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.auto_awesome, size: 18),
              label: Text(_traduciendo ? 'Traduciendo…' : 'Traducir todo al zapoteco (experimental)'),
            )
          else
            _TraduccionExperimental(traduccion: _traduccion!),
          if (_errorTraduccion != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(_errorTraduccion!, style: const TextStyle(fontSize: 13, color: _kTierra)),
            ),
          if (palabras.isNotEmpty) ...[
            const SizedBox(height: 20),
            const Text(
              'En zapoteco',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _kTierra, letterSpacing: 0.5),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [for (final p in palabras) _ChipZapoteco(palabra: p)],
            ),
          ],
          const SizedBox(height: 16),
          Text(
            '${respuesta.despedida} · gracias',
            style: const TextStyle(fontSize: 15, fontStyle: FontStyle.italic, color: _kPrimario),
          ),
          const Divider(height: 28, color: _kBorde),
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 16, color: Color(0xFF555555)),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  respuesta.respaldo == 'sin_conexion'
                      ? '${respuesta.etiquetaModelo} (sin internet)'
                      : respuesta.etiquetaModelo,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF555555)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Traducción completa de Gemma 4, siempre marcada como experimental
class _TraduccionExperimental extends StatelessWidget {
  final TraduccionExperimental traduccion;
  const _TraduccionExperimental({required this.traduccion});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF8E7),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE9C46A)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: const Color(0xFFE9C46A),
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Text(
              'EXPERIMENTAL',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.8),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            traduccion.traduccion,
            style: const TextStyle(fontSize: 17, height: 1.45, fontStyle: FontStyle.italic),
          ),
          const SizedBox(height: 10),
          Text(
            traduccion.aviso,
            style: const TextStyle(fontSize: 12, color: Color(0xFF555555)),
          ),
        ],
      ),
    );
  }
}

/// La respuesta con cada palabra traducida así: "El **Dháh** (frijol) necesita…"
class _FraseConZapoteco extends StatelessWidget {
  final List<Segmento> segmentos;
  const _FraseConZapoteco({required this.segmentos});

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        style: const TextStyle(fontSize: 17, height: 1.45, color: Color(0xFF1A1A1A)),
        children: [
          for (final s in segmentos)
            if (s.zapoteco == null)
              TextSpan(text: s.texto)
            else ...[
              TextSpan(
                text: s.zapoteco,
                style: const TextStyle(fontWeight: FontWeight.w700, color: _kPrimario),
              ),
              TextSpan(
                text: ' (${s.texto})',
                style: const TextStyle(color: Color(0xFF555555)),
              ),
            ],
        ],
      ),
    );
  }
}

class _ChipZapoteco extends StatelessWidget {
  final PalabraZapoteca palabra;
  const _ChipZapoteco({required this.palabra});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: _kPrimarioSuave,
        borderRadius: BorderRadius.circular(20),
      ),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(fontSize: 15, color: _kPrimario),
          children: [
            TextSpan(text: palabra.zapoteco, style: const TextStyle(fontWeight: FontWeight.w700)),
            TextSpan(text: '  ${palabra.espanol.toLowerCase()}', style: const TextStyle(color: Color(0xFF274E3D))),
          ],
        ),
      ),
    );
  }
}
