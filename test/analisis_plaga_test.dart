import 'package:flutter_test/flutter_test.dart';
import 'package:lunisa/data/models/analisis_plaga.dart';

void main() {
  test('lee la respuesta de /analizar-plaga', () {
    final r = AnalisisPlaga.desdeJson({
      'analisis': {
        'es_planta': true,
        'cultivo_visto': 'maíz',
        'parte_afectada': 'hoja',
        'hay_dano': true,
        'sintomas': ['agujeros en las hojas'],
        'posibles_causas': [
          {'nombre': 'gusano cogollero', 'tipo': 'insecto', 'confianza': 'media', 'senales': 'hoyos'},
        ],
        'confianza': 'media',
        'observaciones': 'Daño en el cogollo.',
      },
      'pasos': ['Revisa el revés de las hojas.'],
      'aviso': 'Esto no es un diagnóstico.',
      'zapoteco': [
        {'espanol': 'Gusano', 'zapoteco': 'wexá', 'categoria': 'Plagas', 'variante': 'jaltepec'},
      ],
      'modelo_local': false,
      'proveedor': 'gemini',
      'modelo': 'gemma-4-26b-a4b-it',
    });
    expect(r.causas.single.tipoLegible, 'Insecto');
    expect(r.zapoteco.single.variante, 'jaltepec');
    expect(r.hayDano, isTrue);
    expect(r.etiquetaModelo, 'Revisado con Gemma 4 26B');
  });

  test('hay_dano no_determinable queda en null', () {
    final r = AnalisisPlaga.desdeJson({
      'analisis': {
        'es_planta': true,
        'parte_afectada': 'no_determinable',
        'hay_dano': 'no_determinable',
        'sintomas': [],
        'posibles_causas': [],
        'confianza': 'baja',
        'observaciones': '',
      },
      'proveedor': 'ollama',
      'modelo': 'gemma4:e4b',
    });
    expect(r.hayDano, isNull);
  });
}
