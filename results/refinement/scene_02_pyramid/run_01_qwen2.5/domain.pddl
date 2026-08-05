(define (domain image_block_building)
  (:requirements :strips)

  (:predicates
    (ontable ?x)
    (on ?x ?y)
    (on-bridge ?x ?left ?right)
    (clear ?x)
    (holding ?x)
    (handempty)
    (left-free ?x)
    (right-free ?x)
  )

  (:action pick-up
    :parameters (?x)
    :precondition (and
      (ontable ?x)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (not (ontable ?x))
      (not (clear ?x))
      (not (handempty))
    )
  )

  (:action put-down
    :parameters (?x)
    :precondition (and
      (holding ?x)
    )
    :effect (and
      (ontable ?x)
      (clear ?x)
      (handempty)
      (not (holding ?x))
    )
  )

  (:action stack
    :parameters (?x ?y)
    :precondition (and
      (holding ?x)
      (clear ?y)
    )
    :effect (and
      (on ?x ?y)
      (clear ?x)
      (handempty)
      (not (holding ?x))
      (not (clear ?y))
    )
  )

  (:action unstack
    :parameters (?x ?y)
    :precondition (and
      (on ?x ?y)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (clear ?y)
      (not (on ?x ?y))
      (not (clear ?x))
      (not (handempty))
    )
  )

  (:action stack-bridge
    :parameters (?x ?left ?right)
    :precondition (and
      (holding ?x)
      (right-free ?left)
      (left-free ?right)
    )
    :effect (and
      (on-bridge ?x ?left ?right)
      (clear ?x)
      (handempty)
      (not (holding ?x))
      (not (right-free ?left))
      (not (left-free ?right))
    )
  )

  (:action unstack-bridge
    :parameters (?x ?left ?right)
    :precondition (and
      (on-bridge ?x ?left ?right)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (right-free ?left)
      (left-free ?right)
      (not (on-bridge ?x ?left ?right))
      (not (clear ?x))
      (not (handempty))
    )
  )
)
