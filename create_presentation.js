const PptxGenJS = require('pptxgenjs');
let pres = new PptxGenJS();

pres.layout = 'LAYOUT_16x9';

// Slide 1: Title
let slide = pres.addSlide();
slide.background = { color: '1E2761' }; // Midnight Executive Navy
slide.addText('Agentes Autónomos', { x: 0.5, y: 2.0, w: '90%', fontSize: 44, color: 'FFFFFF', bold: true });
slide.addText('Arquitectura, Inteligencia y Futuro', { x: 0.5, y: 3.0, w: '90%', fontSize: 24, color: 'CADCFC' });

// Slide 2: Definición
slide = pres.addSlide();
slide.addText('¿Qué es un Agente Autónomo?', { x: 0.5, y: 0.5, fontSize: 32, bold: true });
slide.addText(
    'Un sistema de IA capaz de percibir su entorno, razonar, tomar decisiones y ejecutar acciones de forma independiente para lograr objetivos específicos, sin intervención humana constante.',
    { x: 0.5, y: 1.5, w: '90%', fontSize: 18 }
);

// Slide 3: Características clave
slide = pres.addSlide();
slide.addText('Características Clave', { x: 0.5, y: 0.5, fontSize: 32, bold: true });
slide.addText(
    '- Percepción: Capacidad de interactuar con el entorno.\n- Autonomía: Toma de decisiones sin supervisión directa.\n- Planificación: Capacidad de dividir objetivos en tareas.\n- Memoria: Retención de contextos pasados.\n- Adaptabilidad: Ajuste ante cambios en el entorno.',
    { x: 0.5, y: 1.5, w: '90%', fontSize: 18, bullet: true }
);

// Slide 4: Tipos de Agentes
slide = pres.addSlide();
slide.addText('Tipos de Agentes', { x: 0.5, y: 0.5, fontSize: 32, bold: true });
slide.addText(
    '- Agentes de un solo propósito (Reactivos).\n- Agentes basados en modelos (Planificadores).\n- Sistemas Multi-Agente (Colaborativos).\n- Agentes con capacidades de uso de herramientas (Tool-use).',
    { x: 0.5, y: 1.5, w: '90%', fontSize: 18, bullet: true }
);

// Slide 5: Aplicaciones
slide = pres.addSlide();
slide.addText('Aplicaciones', { x: 0.5, y: 0.5, fontSize: 32, bold: true });
slide.addText(
    '- Desarrollo de Software (Generación de código, tests).\n- Investigación y Análisis de datos.\n- Automatización de procesos de negocio (BPA).\n- Soporte al cliente y Gestión de tareas.',
    { x: 0.5, y: 1.5, w: '90%', fontSize: 18, bullet: true }
);

// Slide 6: Desafíos
slide = pres.addSlide();
slide.addText('Desafíos Futuros', { x: 0.5, y: 0.5, fontSize: 32, bold: true });
slide.addText(
    '- Seguridad y Control: Prevención de comportamientos imprevistos.\n- Alineación: Asegurar que los objetivos del agente coincidan con los humanos.\n- Latencia y Recursos: Optimización del razonamiento autónomo.\n- Ética y Responsabilidad.',
    { x: 0.5, y: 1.5, w: '90%', fontSize: 18, bullet: true }
);

pres.writeFile({ fileName: 'Presentacion_Agentes_Autonomos.pptx' });
