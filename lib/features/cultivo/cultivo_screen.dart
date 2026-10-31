import 'dart:io';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/services/backend_service.dart';
import '../../data/models/analisis_cultivo.dart';
import '../../data/models/respuesta_pregunta.dart';

const _kPrimario = Color(0xFF012D1D);
const _kPrimarioSuave = Color(0xFFC1ECD4);
const _kFondo = Color(0xFFFCF9F4);
const _kTierra = Color(0xFF8B5E3C);
const _kBorde = Color(0xFFE5E2DD);
const _kAviso = Color(0xFFFFF8E7);

/// Foto de un cultivo → cómo se ve (etapa y estado) y, si hay daño, posibles causas, con Gemma 4.
/// No es un diagnóstico: los pasos a seguir son fijos y seguros (sin productos ni dosis).
class CultivoScreen extends StatefulWidget {
  const CultivoScreen({super.key});

  @override
  State<CultivoScreen> createState() => _CultivoScreenState();
}

class _CultivoScreenState extends State<CultivoScreen> {
  final _picker = ImagePicker();

  static const _cultivos = ['Maíz', 'Frijol', 'Café', 'Chile', 'Calabaza', 'Tomate', 'Aguacate', 'Palma'];

  String? _cultivo;
  File? _foto;
  bool _analizando = false;
  String? _error;
  AnalisisCultivo? _resultado;

  Future<void> _elegirFoto(ImageSource origen) async {
    final elegida = await _picker.pickImage(source: origen, maxWidth: 1024, imageQuality: 85);
    if (elegida == null) return;
    setState(() {
      _foto = File(elegida.path);
      _resultado = null;
      _error = null;
    });
    await _analizar();
  }

  Future<void> _analizar() async {
    final foto = _foto;
    if (foto == null) return;
    setState(() {
      _analizando = true;
      _error = null;
    });
    try {
      final r = await BackendService.analizarCultivo(foto, cultivo: _cultivo);
      if (mounted) setState(() => _resultado = r);
    } catch (e) {
      debugPrint('[Cultivo] $e');
      if (mounted) {
        setState(() => _error = 'No pudimos revisar la foto. Revisa la conexión con el servidor en Perfil.');
      }
    } finally {
      if (mounted) setState(() => _analizando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
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
          'Revisar mi cultivo',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: _kPrimario),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          children: [
            const Text(
              '¿Qué cultivo es?',
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _kPrimario),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final c in _cultivos)
                  ChoiceChip(
                    label: Text(c),
                    selected: _cultivo == c,
                    selectedColor: _kPrimarioSuave,
                    onSelected: _analizando ? null : (sel) => setState(() => _cultivo = sel ? c : null),
                  ),
              ],
            ),
            const SizedBox(height: 20),
            if (_foto != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(_foto!, height: 220, width: double.infinity, fit: BoxFit.cover),
              )
            else
              Container(
                height: 160,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: _kBorde, width: 1.5),
                ),
                alignment: Alignment.center,
                padding: const EdgeInsets.all(16),
                child: const Text(
                  'Toma una foto de tu planta con buena luz. Si ves algún daño, tómala de cerca.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 15, color: Color(0xFF555555)),
                ),
              ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _analizando ? null : () => _elegirFoto(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera_rounded),
                    label: const Text('Tomar foto'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kPrimario,
                      foregroundColor: Colors.white,
                      minimumSize: const Size.fromHeight(52),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _analizando ? null : () => _elegirFoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Galería'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _kPrimario,
                      minimumSize: const Size.fromHeight(52),
                      side: const BorderSide(color: _kPrimario, width: 1.5),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ),
              ],
            ),
            if (_analizando) ...[
              const SizedBox(height: 24),
              const Center(child: CircularProgressIndicator(color: _kPrimario)),
              const SizedBox(height: 8),
              const Text('Revisando tu cultivo…', textAlign: TextAlign.center),
            ],
            if (_error != null) ...[
              const SizedBox(height: 16),
              _Caja(color: const Color(0xFFFFF3E0), child: Text(_error!)),
            ],
            if (_resultado != null && !_analizando) ...[
              const SizedBox(height: 24),
              _Resultado(r: _resultado!),
            ],
          ],
        ),
      ),
    );
  }
}

class _Resultado extends StatelessWidget {
  final AnalisisCultivo r;
  const _Resultado({required this.r});

  @override
  Widget build(BuildContext context) {
    final color = switch (r.estadoGeneral) {
      'sano' => const Color(0xFF2D6A4F),
      'problemas_serios' => const Color(0xFFB23A2B),
      _ => _kTierra,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(r.titulo, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (r.cultivoVisto != null) _Etiqueta(icono: Icons.eco_outlined, texto: 'Parece ${r.cultivoVisto}'),
            if (r.etapaLegible != null) _Etiqueta(icono: Icons.timeline, texto: r.etapaLegible!),
          ],
        ),
        if (r.observaciones.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(r.observaciones, style: const TextStyle(fontSize: 15, height: 1.4)),
        ],
        const SizedBox(height: 12),
        _Caja(
          color: _kAviso,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.info_outline, color: _kTierra, size: 20),
              const SizedBox(width: 8),
              Expanded(child: Text(r.aviso, style: const TextStyle(fontSize: 13, height: 1.35))),
            ],
          ),
        ),
        if (r.sintomas.isNotEmpty) ...[
          const _Titulo('Daños que se ven'),
          for (final s in r.sintomas)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('•  $s', style: const TextStyle(fontSize: 15, height: 1.35)),
            ),
        ],
        if (r.causas.isNotEmpty) ...[
          const _Titulo('Posibles causas'),
          for (final c in r.causas) _TarjetaCausa(c: c),
        ],
        if (r.pasos.isNotEmpty) ...[
          const _Titulo('Qué hacer ahora'),
          for (var i = 0; i < r.pasos.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  CircleAvatar(
                    radius: 11,
                    backgroundColor: _kPrimarioSuave,
                    child: Text('${i + 1}', style: const TextStyle(fontSize: 12, color: _kPrimario)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(r.pasos[i], style: const TextStyle(fontSize: 15, height: 1.35))),
                ],
              ),
            ),
        ],
        if (r.zapoteco.isNotEmpty) ...[
          const _Titulo('En zapoteco'),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [for (final p in r.zapoteco) _ChipPalabra(p: p)],
          ),
        ],
        const Divider(height: 32, color: _kBorde),
        Row(
          children: [
            const Icon(Icons.auto_awesome, size: 16, color: Color(0xFF555555)),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                r.pieModelo,
                style: const TextStyle(fontSize: 12, color: Color(0xFF555555)),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _Etiqueta extends StatelessWidget {
  final IconData icono;
  final String texto;
  const _Etiqueta({required this.icono, required this.texto});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _kBorde),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icono, size: 16, color: _kPrimario),
          const SizedBox(width: 6),
          Text(texto, style: const TextStyle(fontSize: 13, color: _kPrimario)),
        ],
      ),
    );
  }
}

class _TarjetaCausa extends StatelessWidget {
  final CausaPosible c;
  const _TarjetaCausa({required this.c});

  @override
  Widget build(BuildContext context) {
    final color = switch (c.confianza) {
      'alta' => const Color(0xFFB7E4C7),
      'media' => const Color(0xFFFFE8B0),
      _ => const Color(0xFFEDEDED),
    };
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _kBorde, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  c.nombre,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: _kPrimario),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
                child: Text('Probabilidad ${c.confianza}', style: const TextStyle(fontSize: 11)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(c.tipoLegible, style: const TextStyle(fontSize: 13, color: _kTierra)),
          if (c.senales.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(c.senales, style: const TextStyle(fontSize: 14, height: 1.35)),
          ],
        ],
      ),
    );
  }
}

class _ChipPalabra extends StatelessWidget {
  final PalabraZapoteca p;
  const _ChipPalabra({required this.p});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(color: _kPrimarioSuave, borderRadius: BorderRadius.circular(20)),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(
              style: const TextStyle(fontSize: 15, color: _kPrimario),
              children: [
                TextSpan(text: p.zapoteco, style: const TextStyle(fontWeight: FontWeight.w700)),
                TextSpan(text: '  ${p.espanol.toLowerCase()}'),
              ],
            ),
          ),
          Text(nombreVariante(p.variante), style: const TextStyle(fontSize: 11, color: Color(0xFF555555))),
        ],
      ),
    );
  }
}

class _Titulo extends StatelessWidget {
  final String texto;
  const _Titulo(this.texto);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 20, bottom: 8),
      child: Text(
        texto.toUpperCase(),
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _kTierra, letterSpacing: 0.5),
      ),
    );
  }
}

class _Caja extends StatelessWidget {
  final Color color;
  final Widget child;
  const _Caja({required this.color, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE9C46A)),
      ),
      child: child,
    );
  }
}
