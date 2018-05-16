
# Domination-Game

Para simulación se implementaron varios objetivos
que podían seguir los agentes y de las interacciones
y formas de ordenar las prioridades se implementaron varios
agentes. Estas acciones son:

* Atacar (requiere munición) (requiere un enemigo cerca)
* Capturar Munición
* Capturar `Domination Points`
* Defender `Domination Points`
* Huir (requiere un enemigo cerca)


Se implementaron varios agentes reactivos combinando estas acciones.
Es de notar que la información de munición es local, a diferencia de los
`Domination Points` que es global, por lo tanto en el caso de los agentes
reactivos solo capturan munición si está cerca de estos.
El mejor resultado lo obtuvo ordenando la prioridad de la siguiente manera:


* Atacar (requiere munición) (requiere un enemigo cerca)
* Huir (requiere un enemigo cerca)
* Capturar Munición
* Capturar `Domination Points`
* Defender `Domination Points`

Luego se implementó un agente pro-activo sobre estas mismas acciones,
cuya principales ventaja es la posibilidad de compartir información y por
tanto que 2 agentes no intenten ir por la misma munición, pues solo 1
puede obtenerla, compartir información acerca de la posición de la munición, etc.
A pesar de esto los agentes pro-activos tienden a comportarse peor.


## Discusión

De los agentes programados el mejor comportamiento lo presento el pro-activo, con
la configuración antes descrita. También se experimento con equipos mixto, que mejoraban
los resultados de los agentes pro-activos, pero eran peores a los de agentes reactivos.

Otra consideración importante es el mapa, sobre todo con los agentes pro-activos sucede
que en ciertos mapas ganan en pocos turnos y sin mucha competencia, pero en otros 
pierde con una probabilidad cerca de 50%. En detalle si la partida se extiende más de
200 turnos es probable que dure entre 2000 y 3000 turnos, con mucha fluctuación de la puntuación.

En conclusión falta un análisis más detallado de la influencia del mapa en el juego y 
una revisión de la estrategia e implementación de los agentes pro-activos.