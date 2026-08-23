(define (problem gearbox-adl-precedence-only-problem)

  (:domain gearbox-adl-precedence-only)

  (:objects
    p1 p2 - permanent-component
  )

  (:init
    (precedes p1 p2)
  )

  (:goal
    (and
      (assembled p1)
      (assembled p2)
    )
  )
)