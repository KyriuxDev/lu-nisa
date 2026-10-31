import 'respuesta_pregunta.dart';

/// Posible causa del daño según la foto (no es un diagnóstico)
class CausaPosible {
  final String nombre;

  /// insecto | hongo | bacteria_o_virus | falta_de_nutrientes | clima | otro
  final String tipo;

  /// baja | media | alta
  final String confianza;
  final String senales;

  const CausaPosible({
    required this.nombre,
    required this.tipo,
    required this.confianza,
    required this.senales,
  });

  factory CausaPosible.desdeJson(Map<String, dynamic> json) => CausaPosible(
        nombre: json['nombre'] as String,
        tipo: json['tipo'] as String,
        confianza: json['confianza'] as String,
        senales: json['senales'] as String? ?? '',
      );

  String get tipoLegible => switch (tipo) {
        'insecto' => 'Insecto',
        'hongo' => 'Hongo',
        'bacteria_o_virus' => 'Bacteria o virus',
        'falta_de_nutrientes' => 'Falta de nutrientes',
        'clima' => 'Clima',
        _ => 'Otro',
      };
}

/// Respuesta de POST /analizar-plaga
class AnalisisPlaga {
  final bool esPlanta;
  final String? cultivoVisto;
  final String parteAfectada;

  /// true, false o null si no se pudo saber
  final bool? hayDano;
  final List<String> sintomas;
  final List<CausaPosible> causas;
  final String confianza;
  final String observaciones;
  final List<String> pasos;
  final String aviso;
  final List<PalabraZapoteca> zapoteco;
  final bool modeloLocal;
  final String proveedor;
  final String modelo;

  const AnalisisPlaga({
    required this.esPlanta,
    required this.cultivoVisto,
    required this.parteAfectada,
    required this.hayDano,
    required this.sintomas,
    required this.causas,
    required this.confianza,
    required this.observaciones,
    required this.pasos,
    required this.aviso,
    required this.zapoteco,
    required this.modeloLocal,
    required this.proveedor,
    required this.modelo,
  });

  factory AnalisisPlaga.desdeJson(Map<String, dynamic> json) {
    final a = json['analisis'] as Map<String, dynamic>;
    final dano = a['hay_dano'];
    return AnalisisPlaga(
      esPlanta: a['es_planta'] as bool,
      cultivoVisto: a['cultivo_visto'] as String?,
      parteAfectada: a['parte_afectada'] as String,
      hayDano: dano is bool ? dano : null,
      sintomas: (a['sintomas'] as List? ?? []).cast<String>(),
      causas: (a['posibles_causas'] as List? ?? [])
          .map((e) => CausaPosible.desdeJson(e as Map<String, dynamic>))
          .toList(),
      confianza: a['confianza'] as String,
      observaciones: a['observaciones'] as String? ?? '',
      pasos: (json['pasos'] as List? ?? []).cast<String>(),
      aviso: json['aviso'] as String? ?? '',
      zapoteco: (json['zapoteco'] as List? ?? [])
          .map((e) => PalabraZapoteca.desdeJson(e as Map<String, dynamic>))
          .toList(),
      modeloLocal: json['modelo_local'] as bool? ?? false,
      proveedor: json['proveedor'] as String,
      modelo: json['modelo'] as String,
    );
  }

  String get etiquetaModelo =>
      proveedor == 'gemini' ? 'Revisado con Gemma 4 26B' : 'Revisado con Gemma 4 local';
}
