/// Palabra del glosario zapoteco que apareció en la respuesta o en la pregunta.
class PalabraZapoteca {
  final String espanol;
  final String zapoteco;
  final String categoria;

  const PalabraZapoteca({
    required this.espanol,
    required this.zapoteco,
    required this.categoria,
  });

  factory PalabraZapoteca.desdeJson(Map<String, dynamic> json) => PalabraZapoteca(
        espanol: json['espanol'] as String,
        zapoteco: json['zapoteco'] as String,
        categoria: json['categoria'] as String,
      );
}

/// Respuesta de POST /preguntar.
/// Gemma contesta en español; las palabras en zapoteco las agrega el backend desde el glosario.
class RespuestaPregunta {
  final String pregunta;
  final String respuesta;
  final List<PalabraZapoteca> zapoteco;
  final List<PalabraZapoteca> zapotecoPregunta;
  final String saludo;
  final String despedida;
  final String? municipio;
  final String? respaldo;
  final String proveedor;
  final String modelo;
  final int latenciaMs;

  const RespuestaPregunta({
    required this.pregunta,
    required this.respuesta,
    required this.zapoteco,
    required this.zapotecoPregunta,
    required this.saludo,
    required this.despedida,
    required this.municipio,
    required this.respaldo,
    required this.proveedor,
    required this.modelo,
    required this.latenciaMs,
  });

  factory RespuestaPregunta.desdeJson(String pregunta, Map<String, dynamic> json) {
    List<PalabraZapoteca> lista(String clave) => (json[clave] as List? ?? [])
        .map((e) => PalabraZapoteca.desdeJson(e as Map<String, dynamic>))
        .toList();

    return RespuestaPregunta(
      pregunta: pregunta,
      respuesta: json['respuesta'] as String,
      zapoteco: lista('zapoteco'),
      zapotecoPregunta: lista('zapoteco_pregunta'),
      saludo: json['saludo'] as String? ?? 'Padiuxi',
      despedida: json['despedida'] as String? ?? 'Kixarubalo',
      municipio: json['municipio'] as String?,
      respaldo: json['respaldo'] as String?,
      proveedor: json['proveedor'] as String,
      modelo: json['modelo'] as String,
      latenciaMs: json['latencia_ms'] as int? ?? 0,
    );
  }

  /// Mismo texto que usa el análisis de foto: "Gemma 4 26B" o "Gemma 4 local"
  String get etiquetaModelo =>
      proveedor == 'gemini' ? 'Respondido con Gemma 4 26B' : 'Respondido con Gemma 4 local';
}
