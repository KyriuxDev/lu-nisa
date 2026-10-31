import 'package:flutter_test/flutter_test.dart';
import 'package:lunisa/data/models/analisis_cultivo.dart';

void main() {
  test('lee la respuesta de /analizar-cultivo', () {
    final r = AnalisisCultivo.desdeJson({
      'analisis': {
        'es_planta': true,
        'cultivo_visto': 'maíz',
        'etapa': 'crecimiento',
        'estado_general': 'problemas_leves',
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
    expect(r.titulo, 'Tu cultivo tiene algunos problemas');
    expect(r.etapaLegible, 'En crecimiento');
    expect(r.etiquetaModelo, 'Revisado con Gemma 4 26B');
  });

  test('etapa no_determinable no se muestra', () {
    final r = AnalisisCultivo.desdeJson({
      'analisis': {
        'es_planta': true,
        'etapa': 'no_determinable',
        'estado_general': 'no_determinable',
        'sintomas': [],
        'posibles_causas': [],
        'confianza': 'baja',
        'observaciones': '',
      },
      'proveedor': 'ollama',
      'modelo': 'gemma4:e4b',
    });
    expect(r.etapaLegible, isNull);
    expect(r.titulo, 'No se alcanza a ver bien');
  });

  test('el pie dice por qué respondió el modelo local', () {
    AnalisisCultivo local(String? respaldo) => AnalisisCultivo.desdeJson({
          'analisis': {
            'es_planta': true,
            'etapa': 'crecimiento',
            'estado_general': 'sano',
            'sintomas': [],
            'posibles_causas': [],
            'confianza': 'media',
            'observaciones': '',
          },
          'modelo_local': true,
          'respaldo': respaldo,
          'proveedor': 'ollama',
          'modelo': 'gemma4:e4b',
        });
    expect(local('sin_conexion').pieModelo, contains('sin internet'));
    expect(local('mas_rapido_local').pieModelo, contains('respondió primero'));
  });
}
