create table ROL (
    IdRol serial primary key,
    Nombre varchar(50) not null unique
);
 
create table USUARIO (
    IdUsuario serial primary key,
    Nombres varchar(100) not null,
    ApPat varchar(100) not null,
	ApMat varchar(100) not null,
    Ci varchar(20) unique,
    Correo varchar(150) not null unique,
    PasswordHash varchar(255) not null,
    Telefono varchar(30),
    IdRol integer not null,
    Estado boolean not null default true,
    FechaRegistro timestamp not null default current_timestamp,
 
    constraint fk_usuario_rol foreign key (IdRol) references ROL(IdRol)
);
 
create table ESTUDIANTE (
    IdUsuario integer primary key,
    CodigoEstudiante varchar(50) unique,
    FechaNacimiento date,
    ContactoEmergencia varchar(150),
    TelefonoEmergencia varchar(30),
 
    constraint fk_estudiante_usuario foreign key (IdUsuario) references USUARIO(IdUsuario) on delete cascade
);
 
create table DOCENTE (
    IdUsuario integer primary key,
    Especialidad varchar(150),
 
    constraint fk_docente_usuario foreign key (IdUsuario) references USUARIO(IdUsuario)
        on delete cascade
);
 
create table IDIOMA (
    IdIdioma serial primary key,
    Nombre varchar(100) not null unique,
    Codigo varchar(10) unique,
    Activo boolean not null default true
);
 
create table NIVEL (
    IdNivel serial primary key,
    Codigo varchar(20) not null unique
);
 
create table CURSO (
    IdCurso serial primary key,
    IdIdioma integer not null,
    IdNivel integer not null,
    Nombre varchar(150) not null,
    Descripcion text,
    Activo boolean not null default true,
 
    constraint fk_curso_idioma
        foreign key (IdIdioma)
        references IDIOMA(IdIdioma),
 
    constraint fk_curso_nivel
        foreign key (IdNivel)
        references NIVEL(IdNivel)
);
 
create table PROGRAMA (
    IdPrograma serial primary key,
    Nombre varchar(150) not null,
    DuracionMeses integer,
    Descripcion text,
    Activo boolean not null default true
);
 
create table PROGRAMA_IDIOMA (
    IdProgramaIdioma serial primary key,
    IdPrograma integer not null,
    IdIdioma integer not null,
    NivelMaximoId integer not null,
 
    constraint fk_programa_idioma_programa
        foreign key (IdPrograma)
        references PROGRAMA(IdPrograma)
        on delete cascade,
 
    constraint fk_programa_idioma_idioma
        foreign key (IdIdioma)
        references IDIOMA(IdIdioma),
 
    constraint fk_programa_idioma_nivel
        foreign key (NivelMaximoId)
        references NIVEL(IdNivel),
 
    constraint uq_programa_idioma
        unique (IdPrograma, IdIdioma)
);
 
create table TURNO (
    IdTurno serial primary key,
    Nombre varchar(50) not null unique,
    HoraReferenciaInicio time,
    HoraReferenciaFin time
);
 
create table PARALELO (
    IdParalelo serial primary key,
    Codigo varchar(50) not null unique,
    IdCurso integer not null,
    IdPrograma integer,
    IdTurno integer not null,
    IdDocente integer not null,
    Modalidad varchar(50),
    Aula varchar(100),
    CupoMinimoApertura integer,
    CupoMaximo integer,
    FechaInicio date,
    FechaFin date,
    Estado varchar(30) not null default 'ACTIVO',
 
    constraint fk_paralelo_curso
        foreign key (IdCurso)
        references CURSO(IdCurso),
 
    constraint fk_paralelo_programa
        foreign key (IdPrograma)
        references PROGRAMA(IdPrograma),
 
    constraint fk_paralelo_turno
        foreign key (IdTurno)
        references TURNO(IdTurno),
 
    constraint fk_paralelo_docente
        foreign key (IdDocente)
        references DOCENTE(IdUsuario)
);
 
create table HORARIO_PARALELO (
    IdHorario serial primary key,
    IdParalelo integer not null,
    DiaSemana varchar(20) not null,
    HoraInicio time not null,
    HoraFin time not null,
 
    constraint fk_horario_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade
);
 
create table ESTUDIANTE_PARALELO (
    IdEstudianteParalelo serial primary key,
    IdEstudiante integer not null,
    IdParalelo integer not null,
    FechaIngreso date not null default current_date,
    Estado varchar(30) not null default 'ACTIVO',
 
    constraint fk_estudiante_paralelo_estudiante
        foreign key (IdEstudiante)
        references ESTUDIANTE(IdUsuario)
        on delete cascade,
 
    constraint fk_estudiante_paralelo_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade,
 
    constraint uq_estudiante_paralelo
        unique (IdEstudiante, IdParalelo)
);
 
create table DOCENTE_IDIOMA (
    IdDocenteIdioma serial primary key,
    IdDocente integer not null,
    IdIdioma integer not null,
 
    constraint fk_docente_idioma_docente
        foreign key (IdDocente)
        references DOCENTE(IdUsuario)
        on delete cascade,
 
    constraint fk_docente_idioma_idioma
        foreign key (IdIdioma)
        references IDIOMA(IdIdioma)
        on delete cascade,
 
    constraint uq_docente_idioma
        unique (IdDocente, IdIdioma)
);
 
create table MATERIAL (
    IdMaterial serial primary key,
    IdParalelo integer not null,
    IdDocente integer not null,
    Titulo varchar(200) not null,
    Descripcion text,
    Tipo varchar(50),
    Archivo varchar(500),
    Url varchar(500),
    FechaPublicacion timestamp not null default current_timestamp,
 
    constraint fk_material_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade,
 
    constraint fk_material_docente
        foreign key (IdDocente)
        references DOCENTE(IdUsuario)
);
 
create table ACTIVIDAD (
    IdActividad serial primary key,
    IdParalelo integer not null,
    IdDocente integer not null,
    Titulo varchar(200) not null,
    Instrucciones text,
    Tipo varchar(50),
    FechaPublicacion timestamp not null default current_timestamp,
    FechaLimite timestamp,
    PuntajeMaximo numeric(5,2),
    PermiteEntregaTardia boolean not null default false,
    UsaIa boolean not null default false,
    Estado varchar(30) not null default 'ACTIVA',
 
    constraint fk_actividad_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade,
 
    constraint fk_actividad_docente
        foreign key (IdDocente)
        references DOCENTE(IdUsuario)
);
 
create table ENTREGA (
    IdEntrega serial primary key,
    IdActividad integer not null,
    IdEstudiante integer not null,
    ContenidoTexto text,
    Archivo varchar(500),
    FechaEntrega timestamp not null default current_timestamp,
    EsTardia boolean not null default false,
    Estado varchar(30) not null default 'ENTREGADA',
    Calificacion numeric(5,2),
    Observaciones text,
    FechaCalificacion timestamp,
    IdDocenteCalificador integer,
 
    constraint fk_entrega_actividad
        foreign key (IdActividad)
        references ACTIVIDAD(IdActividad)
        on delete cascade,
 
    constraint fk_entrega_estudiante
        foreign key (IdEstudiante)
        references ESTUDIANTE(IdUsuario)
        on delete cascade,
 
    constraint fk_entrega_docente
        foreign key (IdDocenteCalificador)
        references DOCENTE(IdUsuario)
);
 
create table RETROALIMENTACION_IA (
    IdRetroalimentacion serial primary key,
    IdEntrega integer not null,
    ModeloIa varchar(100),
    TextoOriginal text,
    Correccion text,
    TipoError varchar(100),
    Explicacion text,
    EjerciciosSugeridos text,
    FechaGeneracion timestamp not null default current_timestamp,
 
    constraint fk_retroalimentacion_entrega
        foreign key (IdEntrega)
        references ENTREGA(IdEntrega)
        on delete cascade
);
 
create table SESION_CLASE (
    IdSesion serial primary key,
    IdParalelo integer not null,
    Fecha date not null,
    HoraInicio time,
    HoraFin time,
    Tema varchar(200),
    Tipo varchar(50),
    SalaLivekit varchar(200),
    Estado varchar(30) not null default 'PROGRAMADA',
    InicioReal timestamp,
    FinReal timestamp,
 
    constraint fk_sesion_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade
);
 
create table ASISTENCIA (
    IdAsistencia serial primary key,
    IdSesion integer not null,
    IdEstudiante integer not null,
    Estado varchar(30) not null,
    Observacion varchar(500),
    RegistradoPor integer,
 
    constraint fk_asistencia_sesion
        foreign key (IdSesion)
        references SESION_CLASE(IdSesion)
        on delete cascade,
 
    constraint fk_asistencia_estudiante
        foreign key (IdEstudiante)
        references ESTUDIANTE(IdUsuario)
        on delete cascade,
 
    constraint fk_asistencia_registrado
        foreign key (RegistradoPor)
        references USUARIO(IdUsuario),
 
    constraint uq_asistencia
        unique (IdSesion, IdEstudiante)
);
 
create table SESION_PARTICIPANTE (
    IdParticipante serial primary key,
    IdSesion integer not null,
    IdUsuario integer not null,
    HoraIngreso timestamp,
    HoraSalida timestamp,
 
    constraint fk_participante_sesion
        foreign key (IdSesion)
        references SESION_CLASE(IdSesion)
        on delete cascade,
 
    constraint fk_participante_usuario
        foreign key (IdUsuario)
        references USUARIO(IdUsuario)
        on delete cascade,
 
    constraint uq_sesion_participante
        unique (IdSesion, IdUsuario)
);
 
create table AVISO (
    IdAviso serial primary key,
    IdParalelo integer not null,
    IdDocente integer not null,
    Titulo varchar(200) not null,
    Mensaje text not null,
    FechaPublicacion timestamp not null default current_timestamp,
 
    constraint fk_aviso_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete cascade,
 
    constraint fk_aviso_docente
        foreign key (IdDocente)
        references DOCENTE(IdUsuario)
);
 
create table MENSAJE (
    IdMensaje serial primary key,
    IdEmisor integer not null,
    IdReceptor integer not null,
    IdParalelo integer,
    Contenido text not null,
    FechaEnvio timestamp not null default current_timestamp,
    Leido boolean not null default false,
 
    constraint fk_mensaje_emisor
        foreign key (IdEmisor)
        references USUARIO(IdUsuario)
        on delete cascade,
 
    constraint fk_mensaje_receptor
        foreign key (IdReceptor)
        references USUARIO(IdUsuario)
        on delete cascade,
 
    constraint fk_mensaje_paralelo
        foreign key (IdParalelo)
        references PARALELO(IdParalelo)
        on delete set null
);
 
create table NOTIFICACION (
    IdNotificacion serial primary key,
    IdUsuario integer not null,
    Tipo varchar(50),
    Mensaje text not null,
    Leida boolean not null default false,
    Fecha timestamp not null default current_timestamp,
 
    constraint fk_notificacion_usuario
        foreign key (IdUsuario)
        references USUARIO(IdUsuario)
        on delete cascade
);