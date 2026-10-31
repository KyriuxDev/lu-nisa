import 'package:flutter_test/flutter_test.dart';
import 'package:lunisa/data/models/respuesta_pregunta.dart';

void main() {
  test('lee la respuesta de /preguntar con palabras en zapoteco', () {
    final r = RespuestaPregunta.desdeJson('¿siembro frijol?', {
      'respuesta': 'En octubre suelen llover 141 mm. Por eso el frijol va bien.',
      'zapoteco': [
        {'espanol': 'Frijol', 'zapoteco': 'Dháh', 'categoria': 'Despensa'},
      ],
      'zapoteco_pregunta': [],
      'saludo': 'Padiuxi',
      'despedida': 'Kixarubalo',
      'municipio': 'Ixtlán de Juárez',
      'respaldo': null,
      'proveedor': 'gemini',
      'modelo': 'gemma-4-26b-a4b-it',
      'latencia_ms': 1200,
    });

    expect(r.zapoteco.single.zapoteco, 'Dháh');
    expect(r.etiquetaModelo, 'Respondido con Gemma 4 26B');
    expect(r.pregunta, '¿siembro frijol?');
  });

  test('respaldo local muestra Gemma 4 local', () {
    final r = RespuestaPregunta.desdeJson('hola', {
      'respuesta': 'Hola.',
      'proveedor': 'ollama',
      'modelo': 'gemma4:e4b',
      'respaldo': 'sin_conexion',
    });
    expect(r.etiquetaModelo, 'Respondido con Gemma 4 local');
    expect(r.zapoteco, isEmpty);
    expect(r.saludo, 'Padiuxi');
  });
}
