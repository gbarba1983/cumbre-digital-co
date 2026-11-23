// ============================================
// Validación del formulario en el navegador.
// El servidor vuelve a validar todo; esto solo da respuesta inmediata.
// ============================================
(function () {
  const formulario = document.getElementById('formRegistro');
  if (!formulario) return;

  // Campos del formulario en el orden en que aparecen
  const campos = ['nombre', 'email', 'empresa', 'area'].map(id => document.getElementById(id));

  // Expresión regular para validar el formato del email (igual que en app.py)
  const REGEX_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  // Mensajes de error en español para cada campo vacío
  const MENSAJES_VACIO = {
    nombre: 'El nombre completo es obligatorio.',
    email: 'El email es obligatorio.',
    empresa: 'La empresa u organización es obligatoria.',
    area: 'Selecciona un área de interés.'
  };

  /** Valida un campo, muestra u oculta su error y devuelve true si es válido */
  function validarCampo(campo) {
    const valor = campo.value.trim();
    let mensaje = '';

    if (valor === '') {
      mensaje = MENSAJES_VACIO[campo.id];
    } else if (campo.id === 'email' && !REGEX_EMAIL.test(valor)) {
      mensaje = 'Ingresa un email con formato válido (ej. nombre@empresa.com).';
    }

    mostrarError(campo, mensaje);
    return mensaje === '';
  }

  /** Muestra (o limpia, si el mensaje está vacío) el error de un campo */
  function mostrarError(campo, mensaje) {
    const spanError = document.getElementById('error-' + campo.id);
    spanError.textContent = mensaje;
    campo.classList.toggle('invalido', mensaje !== '');
    campo.setAttribute('aria-invalid', mensaje !== '' ? 'true' : 'false');
  }

  // Validación en vivo: si el campo ya tenía error, se revalida al escribir
  campos.forEach(campo => {
    const evento = campo.tagName === 'SELECT' ? 'change' : 'input';
    campo.addEventListener(evento, () => {
      if (campo.classList.contains('invalido')) validarCampo(campo);
    });
    // Al salir del campo se valida solo si el usuario escribió algo
    campo.addEventListener('blur', () => {
      if (campo.value.trim() !== '') validarCampo(campo);
    });
  });

  // Al enviar: si hay errores se detiene el envío; si no, el formulario va al servidor
  formulario.addEventListener('submit', (evento) => {
    const resultados = campos.map(validarCampo);
    const primerInvalido = campos[resultados.indexOf(false)];

    if (primerInvalido) {
      evento.preventDefault();
      primerInvalido.focus();
    }
  });

  // Si el servidor devolvió errores, llevar el foco al primer campo con error
  const conErrorServidor = campos.find(campo => campo.classList.contains('invalido'));
  if (conErrorServidor) conErrorServidor.focus();
})();
