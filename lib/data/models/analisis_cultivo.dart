import 'respuesta_pregunta.dart';

/// Posible causa de un daño según la foto (no es un diagnóstico)
class CausaPosible {
  final String nombre;

  /// insecto | acaro | hongo | bacteria_o_virus | falta_de_nutrientes | clima | otro
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
        'acaro' => 'Ácaro',
        'hongo' => 'Hongo',
        'bacteria_o_virus' => 'Bacteria o virus',
        'falta_de_nutrientes' => 'Falta de nutrientes',
        'clima' => 'Clima',
        _ => 'Otro',
      };
}

/// Respuesta de POST /analizar-cultivo
class AnalisisCultivo {
  final bool esPlanta;
  final String? cultivoVisto;

  /// plantula | crecimiento | floracion | fruto | madurez | no_determinable
  final String etapa;

  /// sano | problemas_leves | problemas_serios | no_determinable
  final String estadoGeneral;
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

  const AnalisisCultivo({
    required this.esPlanta,
    required this.cultivoVisto,
    required this.etapa,
    required this.estadoGeneral,
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

  factory AnalisisCultivo.desdeJson(Map<String, dynamic> json) {
    final a = json['analisis'] as Map<String, dynamic>;
    return AnalisisCultivo(
      esPlanta: a['es_planta'] as bool,
      cultivoVisto: a['cultivo_visto'] as String?,
      etapa: a['etapa'] as String? ?? 'no_determinable',
      estadoGeneral: a['estado_general'] as String? ?? 'no_determinable',
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

  String? get etapaLegible => switch (etapa) {
        'plantula' => 'Plántula',
        'crecimiento' => 'En crecimiento',
        'floracion' => 'En floración',
        'fruto' => 'Dando fruto',
        'madurez' => 'Lista para cosechar',
        _ => null,
      };

  String get titulo => !esPlanta
      ? 'No vemos una planta en la foto'
      : switch (estadoGeneral) {
          'sano' => 'Tu cultivo se ve sano',
          'problemas_leves' => 'Tu cultivo tiene algunos problemas',
          'problemas_serios' => 'Tu cultivo tiene problemas serios',
          _ => 'No se alcanza a ver bien',
        };

  String get etiquetaModelo =>
      proveedor == 'gemini' ? 'Revisado con Gemma 4 26B' : 'Revisado con Gemma 4 local';
}
